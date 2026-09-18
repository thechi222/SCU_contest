from django.conf import settings
from rest_framework import serializers

from core.models import Artifact, Batch, Event, Job, Node, User
from core.profiles import PROFILES

KIND_CHOICES = list(PROFILES)
STAGES = ["下載輸入", "載入模型", "GPU 運算中", "上傳結果"]


def validate_capabilities(value):
    """只接受通過該機 GPU 自我測試、且模型版本與平台一致的能力回報。"""
    if not isinstance(value, dict) or not set(value) <= set(PROFILES):
        raise serializers.ValidationError("未知的任務能力")
    for kind, capability in value.items():
        if not isinstance(capability, dict) or set(capability) - {"profile", "cuda_verified", "peak_vram_mb"}:
            raise serializers.ValidationError("能力格式不正確")
        if capability.get("profile") != PROFILES[kind] or capability.get("cuda_verified") is not True:
            raise serializers.ValidationError("任務必須先通過 GPU 自我測試")
        peak = capability.get("peak_vram_mb")
        if isinstance(peak, bool) or not isinstance(peak, (int, float)) or not 0 < peak < 1_000_000:
            raise serializers.ValidationError("顯示記憶體測試數據不正確")
    return value


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source="is_staff", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "max_running", "daily_limit", "is_admin"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=12)


class NodeSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.name", read_only=True)
    kinds = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Node
        fields = [
            "id", "name", "owner_name", "is_mine", "gpu_name", "memory_mb", "kinds",
            "sharing", "local_enabled", "revoked", "schedule_start", "schedule_end",
            "utc_offset_minutes", "telemetry", "last_seen",
        ]

    def get_kinds(self, node) -> list[str]:
        return sorted(node.capabilities)

    def get_is_mine(self, node) -> bool:
        request = self.context.get("request")
        return bool(request and node.owner_id == request.user.id)


class NodeUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60, required=False)
    sharing = serializers.BooleanField(required=False)
    revoked = serializers.BooleanField(required=False)
    schedule_start = serializers.RegexField(r"^(?:[01]\d|2[0-3]):[0-5]\d$", required=False, allow_null=True)
    schedule_end = serializers.RegexField(r"^(?:[01]\d|2[0-3]):[0-5]\d$", required=False, allow_null=True)
    utc_offset_minutes = serializers.IntegerField(min_value=-720, max_value=840, required=False)


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = ["id", "name", "media_type", "size"]


class JobSerializer(serializers.ModelSerializer):
    artifacts = ArtifactSerializer(many=True, read_only=True)

    class Meta:
        model = Job
        fields = [
            "id", "batch_id", "kind", "profile", "filename", "input_bytes", "status",
            "stage", "progress", "attempt_count", "error", "artifacts",
            "created_at", "completed_at",
        ]


class BatchSerializer(serializers.ModelSerializer):
    jobs = JobSerializer(many=True, read_only=True)

    class Meta:
        model = Batch
        fields = ["id", "name", "kind", "archived", "created_at", "jobs"]


class BatchCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    name = serializers.CharField(max_length=100)
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)

    def validate_files(self, files):
        if len(files) > settings.MAX_BATCH_FILES:
            raise serializers.ValidationError(f"每批最多 {settings.MAX_BATCH_FILES} 個檔案")
        total = 0
        for uploaded in files:
            if uploaded.size > settings.MAX_FILE_BYTES:
                raise serializers.ValidationError(f"{uploaded.name} 超過單檔上限")
            total += uploaded.size
        if total > settings.MAX_BATCH_BYTES:
            raise serializers.ValidationError("整批檔案超過總量上限")
        return files

    def validate(self, attrs):
        if attrs["kind"] == "upscale":
            for uploaded in attrs["files"]:
                self.check_image(uploaded)
        return attrs

    @staticmethod
    def check_image(uploaded):
        """放大任務只收圖片,並限制原圖尺寸,避免單一工作耗盡顯示記憶體。"""
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(uploaded) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError):
            raise serializers.ValidationError(f"{uploaded.name} 不是可讀的圖片") from None
        finally:
            uploaded.seek(0)

        limit_width, limit_height = settings.MAX_IMAGE_SIZE
        if width > limit_width or height > limit_height:
            raise serializers.ValidationError(
                f"{uploaded.name} 超過 {limit_width}×{limit_height} 的尺寸上限",
            )


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "kind", "message", "created_at"]


class PairSerializer(serializers.Serializer):
    code = serializers.CharField(min_length=8, max_length=64)
    name = serializers.CharField(max_length=60)
    gpu_uuid = serializers.RegexField(r"^[A-Za-z0-9_-]+$", max_length=100)
    gpu_name = serializers.CharField(max_length=120)
    memory_mb = serializers.IntegerField(min_value=1, max_value=1_000_000)
    capabilities = serializers.JSONField(validators=[validate_capabilities])
    environment = serializers.JSONField(required=False, default=dict)


class HeartbeatSerializer(serializers.Serializer):
    attempt_id = serializers.UUIDField(required=False, allow_null=True)
    local_enabled = serializers.BooleanField(default=False)
    capabilities = serializers.JSONField(required=False, default=dict, validators=[validate_capabilities])
    environment = serializers.JSONField(required=False, default=dict)
    telemetry = serializers.JSONField(required=False, default=dict)
    stage = serializers.ChoiceField(choices=STAGES, required=False, allow_null=True)
    progress = serializers.FloatField(min_value=0, max_value=1, required=False, allow_null=True)


class AssignmentSerializer(serializers.Serializer):
    """POST /api/agent/claim 的回傳內容,欄位名稱須與 Agent 端一致。"""

    attempt_id = serializers.UUIDField()
    job_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    profile = serializers.CharField()
    input_url = serializers.CharField()
    input_bytes = serializers.IntegerField()
    lease_seconds = serializers.FloatField()


class HeartbeatResponseSerializer(serializers.Serializer):
    stop = serializers.BooleanField()
    lease_seconds = serializers.FloatField()
    sharing = serializers.BooleanField()
    within_schedule = serializers.BooleanField()


class AttemptFailSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=400)


class AIAssistRequestSerializer(serializers.Serializer):
    message = serializers.CharField()              # 自然語言需求描述


class AIAssistResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()                # 給使用者的自然語言回覆
    batch = BatchSerializer(allow_null=True)       # 若助理代為送出批次則帶回
