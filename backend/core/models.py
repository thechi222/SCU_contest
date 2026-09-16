import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "學生"
        STAFF = "staff", "教職員"

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=Role.choices)   # 無預設值,建立帳號時須指定

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "name", "role"]

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(role__in=["student", "staff"]), name="user_role_valid"),
        ]


class Machine(models.Model):
    class Status(models.TextChoices):
        IDLE = "idle", "閒置"
        BUSY = "busy", "擁有者使用中"
        RENTED = "rented", "租用中"
        OFFLINE = "offline", "離線"

    id = models.CharField(primary_key=True, max_length=50)   # 例如 "lab-gpu-01"
    name = models.CharField(max_length=100)
    cpu_model = models.CharField(max_length=100)
    gpu_model = models.CharField(max_length=100, null=True, blank=True)
    ram_gb = models.IntegerField()
    gpu_vram_gb = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFLINE)
    owner_dept = models.CharField(max_length=100)
    agent_token_hash = models.CharField(                     # Agent token 的 SHA-256,不存明文
        max_length=64, unique=True, null=True, blank=True, editable=False,
    )


class AvailabilityWindow(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="availability_windows")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="window_end_after_start"),
        ]
        indexes = [models.Index(fields=["machine", "start_time"])]


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待開始"
        ACTIVE = "active", "使用中"
        DONE = "done", "已結束"
        CANCELLED = "cancelled", "已取消"
        FAILED = "failed", "開通失敗"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name="bookings")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    access_url = models.URLField(max_length=500, null=True, blank=True)   # 容器開通後才有值

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="booking_end_after_start"),
        ]
        indexes = [models.Index(fields=["machine", "start_time"])]


class AgentHeartbeat(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="heartbeats")
    cpu_percent = models.FloatField()
    ram_percent = models.FloatField()
    gpu_percent = models.FloatField(null=True, blank=True)
    gpu_vram_used_gb = models.FloatField(null=True, blank=True)
    owner_active = models.BooleanField(default=False)        # 機台擁有者正在使用本機
    timestamp = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["machine", "-timestamp"])]


class AgentTask(models.Model):
    class Action(models.TextChoices):
        START = "start", "開通容器"
        STOP = "stop", "回收容器"

    class Status(models.TextChoices):
        PENDING = "pending", "待領取"
        CLAIMED = "claimed", "執行中"
        SUCCEEDED = "succeeded", "成功"
        FAILED = "failed", "失敗"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="tasks")
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="tasks")
    action = models.CharField(max_length=10, choices=Action.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["booking", "action"], name="one_task_per_booking_action"),
        ]
        indexes = [models.Index(fields=["machine", "status", "created_at"])]


class UsageReport(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, primary_key=True, related_name="report",
    )
    duration_hours = models.FloatField()
    cpu_avg = models.FloatField()
    gpu_avg = models.FloatField(null=True, blank=True)
    summary_text = models.TextField()                        # AI 生成的摘要
