from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core.models import (
    AgentHeartbeat, AgentTask, AvailabilityWindow, Booking, Machine, UsageReport, User,
)
from core.tasks import enqueue_task


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
    fieldsets = UserAdmin.fieldsets + (("PowerShare", {"fields": ("name", "role")}),)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "name", "role", "password1", "password2"),
        }),
    )
    list_display = ("email", "name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    ordering = ("email",)


class AvailabilityWindowInline(admin.TabularInline):
    model = AvailabilityWindow
    extra = 1


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "owner_dept")
    inlines = [AvailabilityWindowInline]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "machine", "start_time", "end_time", "status")
    list_filter = ("status", "machine")
    actions = ["enqueue_start_tasks", "enqueue_stop_tasks"]

    @admin.action(description="建立開通任務(由 Agent 領取執行)")
    def enqueue_start_tasks(self, request, queryset):
        for booking in queryset:
            enqueue_task(booking, AgentTask.Action.START)
        self.message_user(request, f"已為 {queryset.count()} 筆預約建立開通任務")

    @admin.action(description="建立回收任務(由 Agent 領取執行)")
    def enqueue_stop_tasks(self, request, queryset):
        for booking in queryset:
            enqueue_task(booking, AgentTask.Action.STOP)
        self.message_user(request, f"已為 {queryset.count()} 筆預約建立回收任務")


@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "machine", "booking", "action", "status", "updated_at")
    list_filter = ("status", "action", "machine")


admin.site.register(AgentHeartbeat)
admin.site.register(UsageReport)
