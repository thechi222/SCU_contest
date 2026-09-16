"""管理指令的測試(README §3.3、§3.4)。"""

import csv
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import AvailabilityWindow, Machine, User


@pytest.mark.django_db
def test_seed_does_not_overwrite_existing_data():
    call_command("seed", stdout=io.StringIO())
    Machine.objects.filter(id="lab-gpu-01").update(status="offline")
    call_command("seed", stdout=io.StringIO())

    assert Machine.objects.get(id="lab-gpu-01").status == "offline"
    assert AvailabilityWindow.objects.filter(machine_id="lab-gpu-01").count() == 1
    assert not User.objects.exists()


@pytest.mark.django_db
def test_import_users_creates_accounts_with_random_passwords(tmp_path):
    source = tmp_path / "accounts.csv"
    source.write_text(
        "email,name,role\nTester1@scu.edu.tw,受測者一,student\ntester2@scu.edu.tw,受測者二,staff\n",
        encoding="utf-8",
    )
    output = tmp_path / "credentials.csv"

    call_command("import_users", str(source), output=str(output), stdout=io.StringIO())

    with output.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [row["email"] for row in rows] == ["tester1@scu.edu.tw", "tester2@scu.edu.tw"]
    assert rows[0]["password"] != rows[1]["password"]
    assert User.objects.get(email="tester1@scu.edu.tw").check_password(rows[0]["password"])


@pytest.mark.django_db
def test_import_users_rejects_invalid_role(tmp_path):
    source = tmp_path / "accounts.csv"
    source.write_text("email,name,role\nguest@example.com,訪客,external\n", encoding="utf-8")
    output = tmp_path / "credentials.csv"

    with pytest.raises(CommandError):
        call_command("import_users", str(source), output=str(output), stdout=io.StringIO())

    assert not output.exists()
    assert not User.objects.exists()
