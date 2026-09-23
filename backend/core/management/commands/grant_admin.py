from django.core.management.base import BaseCommand, CommandError

from core.models import User, normalize_student_id


class Command(BaseCommand):
    help = "Grant or revoke platform admin rights by student ID (README §4.11)."

    def add_arguments(self, parser):
        parser.add_argument("student_id", nargs="+", help="學號或員工編號,可一次指定多個")
        parser.add_argument("--revoke", action="store_true", help="改為移除管理權限")

    def handle(self, *args, student_id, revoke, **options):
        grant = not revoke
        for raw in student_id:
            identifier = normalize_student_id(raw)
            user = User.objects.filter(student_id=identifier).first()
            if user is None:
                raise CommandError(f"找不到帳號 {identifier}")
            user.is_staff = grant
            user.is_superuser = grant
            if grant:
                user.is_active = True
            user.save(update_fields=["is_staff", "is_superuser", "is_active"])
            state = "已設為管理員" if grant else "已移除管理權限"
            self.stdout.write(f"{identifier}({user.name}):{state}")
