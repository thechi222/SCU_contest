import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User
from core.seed_data import SEED_USERS


class Command(BaseCommand):
    help = "Create local demo accounts with random passwords. Existing accounts are never modified."

    @transaction.atomic
    def handle(self, *args, **options):
        for data in SEED_USERS:
            if User.objects.filter(student_id=data["student_id"]).exists():
                self.stdout.write(f"user {data['student_id']}: exists, unchanged")
                continue
            password = secrets.token_urlsafe(12)
            User.objects.create_user(password=password, **data)
            self.stdout.write(f"user {data['student_id']}: created, password {password}")

        self.stdout.write(
            "GPU 節點不由 seed 建立;請於網站取得配對碼後,在機台執行 agent pair。"
        )
