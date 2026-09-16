from django.core.management.base import BaseCommand

from core.models import Machine, User
from core.seed_data import SEED_MACHINES, SEED_PASSWORD, SEED_USERS


class Command(BaseCommand):
    help = "Load seed machines and demo accounts (README §4.7). Safe to re-run."

    def handle(self, *args, **options):
        for data in SEED_MACHINES:
            Machine.objects.update_or_create(id=data["id"], defaults=data)

        for data in SEED_USERS:
            user, created = User.objects.update_or_create(
                email=data["email"],
                defaults={**data, "username": data["email"]},
            )
            if created:
                user.set_password(SEED_PASSWORD)
                user.save(update_fields=["password"])

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(SEED_MACHINES)} machines and {len(SEED_USERS)} demo accounts."
        ))
