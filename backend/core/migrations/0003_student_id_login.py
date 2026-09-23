"""改以學號登入(README §4.1、§4.11)。

既有帳號沒有學號,先以信箱前綴推導一組暫時值並確保唯一,再改為必填的唯一欄位;
實際的學號請由管理者於 Django Admin 更正。
"""

import re

import django.core.validators
from django.db import migrations, models

import core.models


def fill_student_ids(apps, schema_editor):
    User = apps.get_model("core", "User")
    taken = set()
    for user in User.objects.all().order_by("pk"):
        source = (user.email or user.username or "").split("@")[0]
        base = re.sub(r"[^A-Za-z0-9]", "", source).upper()[:20]
        if len(base) < 4:
            base = f"USER{user.pk:04d}"
        candidate, index = base, 1
        while candidate in taken:
            suffix = str(index)
            candidate = base[: 20 - len(suffix)] + suffix
            index += 1
        taken.add(candidate)
        user.student_id = candidate
        user.username = candidate
        user.save(update_fields=["student_id", "username"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_usage_and_rentals"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[("objects", core.models.UserManager())],
        ),
        migrations.AddField(
            model_name="user",
            name="student_id",
            field=models.CharField(max_length=20, null=True),
        ),
        migrations.RunPython(fill_student_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="student_id",
            field=models.CharField(
                max_length=20,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        "^[A-Za-z0-9]{4,20}$", "學號應為 4–20 碼英數字",
                    ),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=models.Q(("email", ""), _negated=True),
                fields=("email",),
                name="unique_email_when_set",
            ),
        ),
    ]
