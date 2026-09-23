import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from core.profiles import PROFILES


def job_input_path(instance, filename):
    return f"inputs/{instance.id}/source"


def artifact_path(instance, filename):
    return f"artifacts/{instance.job_id}/{instance.id}/{filename}"


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "學生"
        STAFF = "staff", "教職員"

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=Role.choices)   # 無預設值,建立帳號時須指定
    max_running = models.PositiveSmallIntegerField(default=2)      # 同時執行中的工作上限
    daily_limit = models.PositiveIntegerField(default=100)         # 每日提交檔案數上限
    last_dispatch = models.BigIntegerField(default=0)              # 公平派工用的序號,越小越優先

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "name", "role"]

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=["student", "staff"]), name="user_role_valid"),
        ]


class Node(models.Model):
    """一張參與共享的 GPU。由 Agent 以一次性配對碼登錄。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="nodes")
    name = models.CharField(max_length=60)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)   # 節點 token 的 SHA-256
    gpu_uuid = models.CharField(max_length=100, unique=True)
    gpu_name = models.CharField(max_length=120)
    memory_mb = models.PositiveIntegerField()
    capabilities = models.JSONField(default=dict)   # {kind: {profile, cuda_verified, peak_vram_mb}}
    environment = models.JSONField(default=dict)    # 驅動、作業系統、容器 image ID 等佐證
    telemetry = models.JSONField(default=dict)      # 最近一次心跳的 GPU 監控數值
    sharing = models.BooleanField(default=False)        # 平台端開關,由機主於網站切換
    local_enabled = models.BooleanField(default=False)  # 機台端開關,由 Agent 的 ENABLED 檔回報
    allow_rental = models.BooleanField(default=False)   # 機主另行同意才接受互動式租借
    revoked = models.BooleanField(default=False)        # 撤銷後 token 失效
    schedule_start = models.CharField(max_length=5, null=True, blank=True)   # "HH:MM",空值代表不限時段
    schedule_end = models.CharField(max_length=5, null=True, blank=True)
    utc_offset_minutes = models.SmallIntegerField(default=480)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PairingCode(models.Model):
    """一次性配對碼,只存雜湊,預設 10 分鐘內有效。"""

    code_hash = models.CharField(max_length=64, primary_key=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pairing_codes")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class Batch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="batches")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=[(k, k) for k in PROFILES])
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "排隊中"
        LOADING = "loading", "準備中"
        RUNNING = "running", "執行中"
        RETRYING = "retrying", "重新排隊"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失敗"
        CANCELLED = "cancelled", "已取消"

    ACTIVE = ("loading", "running")
    PENDING = ("queued", "retrying")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="jobs")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="jobs")
    kind = models.CharField(max_length=10, choices=[(k, k) for k in PROFILES])
    profile = models.CharField(max_length=40)          # 送出時固定的模型版本
    filename = models.CharField(max_length=255)        # 使用者原始檔名,僅供顯示
    input_file = models.FileField(upload_to=job_input_path, max_length=255)
    input_bytes = models.PositiveBigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=20, default="等待可用設備")
    progress = models.FloatField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]


class Attempt(models.Model):
    """一次派工。租約到期或節點停止後結束,工作重新排隊。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="attempts")
    node = models.ForeignKey(Node, on_delete=models.PROTECT, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    lease_until = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=20, blank=True)   # succeeded / failed / expired / cancelled
    error = models.TextField(blank=True)
    gpu_verified = models.BooleanField(default=False)
    metrics = models.JSONField(default=dict)                # worker 回報的 gpu_seconds、engine 等

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["node"], condition=models.Q(ended_at__isnull=True), name="one_active_attempt_per_node",
            ),
            models.UniqueConstraint(
                fields=["job"], condition=models.Q(ended_at__isnull=True), name="one_active_attempt_per_job",
            ),
        ]
        indexes = [models.Index(fields=["ended_at", "lease_until"])]


class Artifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="artifacts")
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to=artifact_path, max_length=255)
    media_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()


class Rental(models.Model):
    """互動式租借:使用者在限定時間內取得一個固定映像的 GPU 容器,自行操作。

    與 Job 共用同一批節點,但一台節點同時只會有一件工作或一段租借(見 §4.5)。
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "排隊中"
        STARTING = "starting", "啟動中"
        ACTIVE = "active", "使用中"
        ENDING = "ending", "結束中"
        ENDED = "ended", "已結束"
        EXPIRED = "expired", "已到期"
        FAILED = "failed", "啟動失敗"
        CANCELLED = "cancelled", "已取消"

    OPEN = ("queued", "starting", "active", "ending")   # 仍佔用佇列或節點
    ON_NODE = ("starting", "active", "ending")          # 已指派節點

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="rentals")
    node = models.ForeignKey(Node, on_delete=models.PROTECT, null=True, blank=True, related_name="rentals")
    workspace = models.CharField(max_length=20)         # WORKSPACES 的鍵
    image = models.CharField(max_length=120)            # 申請時固定的映像版本
    minutes = models.PositiveSmallIntegerField()        # 申請時數(分鐘)
    purpose = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    connect_url = models.CharField(max_length=300, blank=True)   # Agent 回報的連線位址
    connect_token = models.CharField(max_length=120, blank=True)  # 只給租借者,結束時清除
    connection = models.JSONField(default=dict)         # 通道型態與其他連線資訊
    lease_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["node"],
                condition=models.Q(status__in=["starting", "active", "ending"]),
                name="one_open_rental_per_node",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]


class UsageSample(models.Model):
    """節點狀態取樣。心跳時每 settings.USAGE_SAMPLE_SECONDS 最多寫入一筆,供儀表板繪圖與匯出。"""

    class State(models.TextChoices):
        BUSY = "busy", "執行工作"
        RENTED = "rented", "租借中"
        IDLE = "idle", "閒置可用"
        PAUSED = "paused", "未開放"
        OFFLINE = "offline", "離線"

    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="usage_samples")
    captured_at = models.DateTimeField()
    state = models.CharField(max_length=10, choices=State.choices)
    gpu_utilization = models.FloatField(null=True, blank=True)        # 0–100
    memory_used_mb = models.PositiveIntegerField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    power_w = models.FloatField(null=True, blank=True)
    interval_seconds = models.FloatField(default=0)   # 距離上一筆取樣的秒數
    busy_seconds = models.FloatField(default=0)       # 區間內視為有工作的秒數

    class Meta:
        indexes = [
            models.Index(fields=["node", "-captured_at"]),
            models.Index(fields=["-captured_at"]),
        ]


class NodeDailyUsage(models.Model):
    """每日用量彙整。取樣資料會定期清除,長期統計以本表保存。"""

    id = models.BigAutoField(primary_key=True)
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="daily_usage")
    day = models.DateField()
    busy_seconds = models.FloatField(default=0)
    rented_seconds = models.FloatField(default=0)
    idle_seconds = models.FloatField(default=0)
    offline_seconds = models.FloatField(default=0)
    gpu_seconds = models.FloatField(default=0)        # worker 回報的實際 GPU 執行秒數
    jobs_completed = models.PositiveIntegerField(default=0)
    samples = models.PositiveIntegerField(default=0)
    avg_utilization = models.FloatField(null=True, blank=True)
    peak_utilization = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["node", "day"], name="one_usage_row_per_node_day"),
        ]
        indexes = [models.Index(fields=["-day"])]


class Event(models.Model):
    """稽核紀錄。使用者只看得到與自己的工作或設備相關的事件。"""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    node = models.ForeignKey(Node, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    kind = models.CharField(max_length=40)
    message = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-id"])]
