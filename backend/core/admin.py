from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core import services
from core.models import Artifact, Attempt, Batch, Event, Job, Node, User


# 內建使用者表單綁定 auth.User,自訂使用者模型須另行指定
class PowerShareUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "username", "name", "role")


class PowerShareUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


@admin.register(User)
class PowerShareUserAdmin(UserAdmin):
    form = PowerShareUserChangeForm
    add_form = PowerShareUserCreationForm
    fieldsets = UserAdmin.fieldsets + (
        ("PowerShare", {"fields": ("name", "role", "max_running", "daily_limit")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "name", "role", "password1", "password2"),
        }),
    )
    list_display = ("email", "name", "role", "max_running", "daily_limit", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    ordering = ("email",)


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "gpu_name", "sharing", "local_enabled", "revoked", "last_seen")
    list_filter = ("sharing", "revoked")
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


admin.site.register(Batch)
admin.site.register(Artifact)
