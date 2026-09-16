from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from core.models import (
    AgentHeartbeat, AgentTask, AvailabilityWindow, Booking, Machine, UsageReport, User,
)

START_TIME_TOLERANCE = timedelta(minutes=5)   # 容許表單送出前的填寫時間差


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "role"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = [
            "id", "name", "cpu_model", "gpu_model", "ram_gb",
            "gpu_vram_gb", "status", "owner_dept",
        ]


class AvailabilityWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityWindow
        fields = ["start_time", "end_time"]


class BookingCreateSerializer(serializers.Serializer):
    machine_id = serializers.CharField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "結束時間必須晚於開始時間"})
        if attrs["start_time"] < timezone.now() - START_TIME_TOLERANCE:
            raise serializers.ValidationError({"start_time": "開始時間不得早於現在"})
        return attrs


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            "id", "user_id", "machine_id", "start_time", "end_time",
            "status", "access_url",
        ]


class AgentHeartbeatSerializer(serializers.ModelSerializer):
    machine_id = serializers.PrimaryKeyRelatedField(
        source="machine", queryset=Machine.objects.all(),
    )

    class Meta:
        model = AgentHeartbeat
        fields = [
            "machine_id", "cpu_percent", "ram_percent", "gpu_percent",
            "gpu_vram_used_gb", "owner_active", "timestamp",
        ]


class AgentTaskSerializer(serializers.ModelSerializer):
    end_time = serializers.DateTimeField(source="booking.end_time", read_only=True)

    class Meta:
        model = AgentTask
        fields = ["id", "booking_id", "action", "end_time"]


class AgentTaskResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["succeeded", "failed"])
    access_url = serializers.URLField(max_length=500, required=False, allow_null=True)   # start 成功時必填
    error_message = serializers.CharField(required=False, allow_blank=True)             # failed 時填寫原因


class UsageReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsageReport
        fields = ["booking_id", "duration_hours", "cpu_avg", "gpu_avg", "summary_text"]


class AIAssistRequestSerializer(serializers.Serializer):
    message = serializers.CharField()              # 自然語言需求描述


class AIAssistResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()                # 給使用者的自然語言回覆
    booking = BookingSerializer(allow_null=True)   # 成功建立預約時帶回
