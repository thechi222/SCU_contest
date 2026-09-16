from rest_framework import serializers

from core.models import AgentHeartbeat, Booking, Machine, UsageReport, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "credit"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = [
            "id", "name", "cpu_model", "gpu_model", "ram_gb",
            "gpu_vram_gb", "status", "owner_dept", "price_per_hour",
        ]


class BookingCreateSerializer(serializers.Serializer):
    machine_id = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id", "user_id", "machine_id", "start_time", "end_time",
            "status", "access_url", "estimated_cost",
        ]


class AgentHeartbeatSerializer(serializers.ModelSerializer):
    machine_id = serializers.PrimaryKeyRelatedField(
        source="machine", queryset=Machine.objects.all(),
    )

    class Meta:
        model = AgentHeartbeat
        fields = [
            "machine_id", "cpu_percent", "ram_percent",
            "gpu_percent", "gpu_vram_used_gb", "timestamp",
        ]


class UsageReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageReport
        fields = [
            "booking_id", "duration_hours", "cpu_avg",
            "gpu_avg", "cost", "summary_text",
        ]


class AIAssistRequestSerializer(serializers.Serializer):
    message = serializers.CharField()              # 自然語言需求描述


class AIAssistResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()                # 給使用者的自然語言回覆
    booking = BookingSerializer(allow_null=True)   # 成功建立預約時帶回
