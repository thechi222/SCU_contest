from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core.models import AgentHeartbeat, Booking, Machine, UsageReport, User


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
    fieldsets = UserAdmin.fieldsets + (("PowerShare", {"fields": ("name", "role", "credit")}),)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "name", "role", "password1", "password2"),
        }),
    )
    list_display = ("email", "name", "role", "credit", "is_staff")
    ordering = ("email",)


admin.site.register(Machine)
admin.site.register(Booking)
admin.site.register(AgentHeartbeat)
admin.site.register(UsageReport)
