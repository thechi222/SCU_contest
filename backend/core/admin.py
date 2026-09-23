from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core import rentals as rental_service
from core import services
from core.models import (
    Artifact, Attempt, Batch, Event, Job, Node, NodeDailyUsage, Rental, UsageSample, User,
    normalize_student_id,
)


# 內建使用者表單綁定 auth.User,自訂使用者模型須另行指定
class PowerShareUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("student_id", "name", "role", "email")

    def save(self, commit=True):
        # 帳號識別為學號;AbstractUser 的 username 一律填入相同值
        user = super().save(commit=False)
        user.student_id = normalize_student_id(user.student_id)
        user.username = user.student_id
        user.email = user.email or ""
        if commit:
            user.save()
        return user


class PowerShareUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class PowerShareUserAdmin(UserAdmin):
    form = PowerShareUserChangeForm
    add_form = PowerShareUserCreationForm
    fieldsets = (
        (None, {"fields": ("student_id", "password")}),
        ("PowerShare", {"fields": ("name", "role", "email", "max_running", "daily_limit")}),
        ("權限", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("重要日期", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("student_id", "name", "role", "email", "password1", "password2"),
        }),
    )
    list_display = (
        "student_id", "name", "role", "is_active", "max_running", "daily_limit", "is_staff",
    )
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("student_id", "name", "email")
    ordering = ("student_id",)
    actions = ["approve_users"]

    @admin.action(description="核可帳號(啟用登入)")
    def approve_users(self, request, queryset):
        approved = queryset.filter(is_active=False).update(is_active=True)
        self.message_user(request, f"已核可 {approved} 個帳號")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = (
        "name", "owner", "gpu_name", "sharing", "local_enabled", "allow_rental", "revoked", "last_seen",
    )
    list_filter = ("sharing", "allow_rental", "revoked")
    readonly_fields = ("token_hash", "capabilities", "environment", "telemetry", "last_seen")
    actions = ["revoke_nodes"]

    @admin.action(description="撤銷設備(使其 token 失效)")
    def revoke_nodes(self, request, queryset):
        for node in queryset:
            node.revoked = True
            node.sharing = False
            node.save(update_fields=["revoked", "sharing"])
            services.record("node", f"{node.name} 由管理者撤銷", user=node.owner, node=node)
        self.message_user(request, f"已撤銷 {queryset.count()} 台設備")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("filename", "user", "kind", "status", "stage", "attempt_count", "created_at")
    list_filter = ("status", "kind")
    readonly_fields = ("input_file", "input_bytes", "profile")
    actions = ["cancel_jobs"]

    @admin.action(description="取消工作")
    def cancel_jobs(self, request, queryset):
        cancelled = 0
        for job in queryset:
            try:
                services.cancel_job(job.user, job.id)
                cancelled += 1
            except Exception as error:   # 已結束的工作略過
                self.message_user(request, f"{job.filename}:{error}")
        self.message_user(request, f"已取消 {cancelled} 件工作")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "node", "started_at", "lease_until", "ended_at", "outcome", "gpu_verified")
    list_filter = ("outcome", "gpu_verified", "node")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "message", "user", "node", "job")
    list_filter = ("kind",)


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "workspace", "node", "status", "minutes", "created_at", "expires_at")
    list_filter = ("status", "workspace")
    readonly_fields = ("connect_url", "connect_token", "connection", "lease_until")
    actions = ["end_rentals"]

    @admin.action(description="結束租借(容器於下一次心跳停止)")
    def end_rentals(self, request, queryset):
        ended = 0
        for rental in queryset.filter(status__in=Rental.OPEN):
            rental_service.finish(rental, Rental.Status.ENDED, "管理者結束")
            ended += 1
        self.message_user(request, f"已結束 {ended} 段租借")


@admin.register(NodeDailyUsage)
class NodeDailyUsageAdmin(admin.ModelAdmin):
    list_display = ("day", "node", "busy_seconds", "rented_seconds", "idle_seconds",
                    "gpu_seconds", "jobs_completed", "avg_utilization")
    list_filter = ("day", "node")


@admin.register(UsageSample)
class UsageSampleAdmin(admin.ModelAdmin):
    list_display = ("captured_at", "node", "state", "gpu_utilization", "memory_used_mb", "busy_seconds")
    list_filter = ("state", "node")


admin.site.register(Batch)
admin.site.register(Artifact)
