import secrets
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import AvailabilityWindow, Machine, User
from core.seed_data import SEED_AVAILABILITY_DAYS, SEED_MACHINES, SEED_USERS


class Command(BaseCommand):
    help = "Create seed machines (README §4.8). Existing records are never modified."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo-users", action="store_true",
            help="Also create demo accounts with random passwords (local development only).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        for data in SEED_MACHINES:
            machine, created = Machine.objects.get_or_create(id=data["id"], defaults=data)
            if created:
                AvailabilityWindow.objects.create(
                    machine=machine, start_time=today,
                    end_time=today + timedelta(days=SEED_AVAILABILITY_DAYS),
                )
            self.stdout.write(f"machine {machine.id}: {'created' if created else 'exists, unchanged'}")

        if not options["demo_users"]:
            return
        for data in SEED_USERS:
            if User.objects.filter(email=data["email"]).exists():
                self.stdout.write(f"user {data['email']}: exists, unchanged")
                continue
            password = secrets.token_urlsafe(12)
            User.objects.create_user(username=data["email"], password=password, **data)
            self.stdout.write(f"user {data['email']}: created, password {password}")
