"""管理指令的測試(README §3.3、§3.4)。"""

import csv
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import User


@pytest.mark.django_db
def test_seed_creates_demo_accounts_once():
    call_command("seed", stdout=io.StringIO())
    User.objects.filter(email="demo.student@scu.edu.tw").update(name="改過的名字")
    call_command("seed", stdout=io.StringIO())

    assert User.objects.count() == 2
    assert User.objects.get(email="demo.student@scu.edu.tw").name == "改過的名字"


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
