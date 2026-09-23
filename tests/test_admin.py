"""管理台的權限與帳號管理測試(README §4.12)。"""

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(make_user):
    return make_user(student_id="ADMIN001", role="staff", name="管理員", is_staff=True)


def test_overview_requires_admin(client, user):
    client.force_login(user)

    response = client.get("/api/admin/overview")

    assert response.status_code == 403 and response.json()["code"] == "PERMISSION_DENIED"


def test_overview_requires_login(client):
    assert client.get("/api/admin/overview").json()["code"] == "NOT_AUTHENTICATED"


def test_overview_lists_accounts_and_usage(client, admin, make_user, make_job):
    student = make_user(student_id="11172001", name="王小明")
    make_job(student)
    make_user(student_id="11172002", name="待審核", is_active=False)
    client.force_login(admin)

    body = client.get("/api/admin/overview").json()

    assert body["summary"]["users_total"] == 3
    assert body["summary"]["users_pending"] == 1
    assert body["summary"]["users_admin"] == 1
    assert [row["student_id"] for row in body["pending_users"]] == ["11172002"]
    listed = {row["student_id"]: row for row in body["users"]}
    assert listed["11172001"]["jobs_total"] == 1
    assert body["jobs"][0]["user"] == "11172001"
    assert "nodes_online" in body["usage"]


def test_admin_can_approve_a_pending_account(client, admin, make_user):
    pending = make_user(student_id="11172003", name="待審核", is_active=False)
    client.force_login(admin)

    response = client.patch(
        f"/api/admin/users/{pending.id}", {"is_active": True}, content_type="application/json",
    )

    assert response.status_code == 200 and response.json()["is_active"] is True
    pending.refresh_from_db()
    assert pending.is_active is True


def test_admin_can_grant_admin_rights_and_adjust_quota(client, admin, make_user):
    teammate = make_user(student_id="11172004", name="組員")
    client.force_login(admin)

    response = client.patch(
        f"/api/admin/users/{teammate.id}",
        {"is_admin": True, "max_running": 4, "daily_limit": 300},
        content_type="application/json",
    )

    assert response.status_code == 200
    teammate.refresh_from_db()
    assert teammate.is_staff and teammate.max_running == 4 and teammate.daily_limit == 300


def test_admin_cannot_lock_themselves_out(client, admin):
    client.force_login(admin)

    removed = client.patch(
        f"/api/admin/users/{admin.id}", {"is_admin": False}, content_type="application/json",
    )
    disabled = client.patch(
        f"/api/admin/users/{admin.id}", {"is_active": False}, content_type="application/json",
    )

    assert removed.status_code == 400 and disabled.status_code == 400
    admin.refresh_from_db()
    assert admin.is_staff and admin.is_active


def test_non_admin_cannot_change_accounts(client, user, make_user):
    target = make_user(student_id="11172005", name="其他人")
    client.force_login(user)

    response = client.patch(
        f"/api/admin/users/{target.id}", {"is_admin": True}, content_type="application/json",
    )

    assert response.status_code == 403
    target.refresh_from_db()
    assert target.is_staff is False


def test_grant_admin_command(make_user):
    teammate = make_user(student_id="11172006", name="組員", is_active=False)

    call_command("grant_admin", "1117-2006", stdout=io.StringIO())

    teammate.refresh_from_db()
    assert teammate.is_staff and teammate.is_superuser and teammate.is_active

    call_command("grant_admin", "11172006", revoke=True, stdout=io.StringIO())
    teammate.refresh_from_db()
    assert teammate.is_staff is False


def test_grant_admin_command_rejects_unknown_account():
    with pytest.raises(CommandError):
        call_command("grant_admin", "99999999", stdout=io.StringIO())

    assert not User.objects.filter(student_id="99999999").exists()
