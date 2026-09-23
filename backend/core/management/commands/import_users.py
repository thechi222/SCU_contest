import csv
import secrets
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import User, normalize_student_id


class Command(BaseCommand):
    help = (
        "Create accounts from a CSV with columns student_id,name,role[,email]. "
        "Generated passwords are written to --output, which must not already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--output", required=True)

    def handle(self, *args, csv_path, output, **options):
        output_path = Path(output)
        if output_path.exists():
            raise CommandError(f"{output_path} already exists")

        users, credentials = [], []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for line_no, row in enumerate(csv.DictReader(f), start=2):
                student_id = normalize_student_id(row["student_id"])
                email = (row.get("email") or "").strip().lower()
                password = secrets.token_urlsafe(12)
                user = User(
                    student_id=student_id, username=student_id, email=email,
                    name=row["name"].strip(), role=row["role"].strip(),
                )
                user.set_password(password)
                try:
                    user.full_clean()
                except ValidationError as exc:
                    raise CommandError(f"line {line_no} ({student_id}): {exc.messages}") from exc
                users.append(user)
                credentials.append({"student_id": student_id, "password": password})

        with open(output_path, "x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["student_id", "password"])
            writer.writeheader()
            writer.writerows(credentials)

        try:
            with transaction.atomic():
                for user in users:
                    user.save()
        except Exception:
            output_path.unlink()
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Created {len(users)} accounts; credentials written to {output_path}"
        ))
