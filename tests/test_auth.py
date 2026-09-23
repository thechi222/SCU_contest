"""註冊與以學號登入的測試(README §4.11)。"""

import pytest
from django.core.cache import cache

from core.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


PASSWORD = "Gpu2026share"      # 至少 6 碼,含英文大寫與數字


def register(client, **overrides):
    payload = {
        "student_id": "11172001", "name": "測試學生", "role": "student",
        "password": PASSWORD, **overrides,
    }
    return client.post("/api/auth/register", payload, content_type="application/json")


def test_register_creates_account_and_signs_in(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json()["student_id"] == "11172001"
    user = User.objects.get(student_id="11172001")
    assert user.is_active and user.username == "11172001" and user.email == ""
    assert client.get("/api/auth/me").json()["student_id"] == "11172001"   # 已建立 session


def test_student_id_is_normalised(client):
    assert register(client, student_id=" 1117-2001 ").status_code == 201

    assert User.objects.filter(student_id="11172001").exists()


def test_register_rejects_duplicate_student_id(client, make_user):
    make_user(student_id="11172001")

    response = register(client)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("student_id", ["1117200", "111720011", "A1172001", "11@7"])
def test_student_number_must_be_eight_digits(client, student_id):
    response = register(client, student_id=student_id)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_staff_may_use_an_employee_number(client):
    response = register(client, student_id="STAFF-012", role="staff", name="張老師")

    assert response.status_code == 201
    assert User.objects.get(student_id="STAFF012").role == "staff"


@pytest.mark.parametrize("name", ["王小明", "Chen Wei-Ting", "李 小 龍"])
def test_name_accepts_chinese_and_english(client, name):
    assert register(client, name=name).status_code == 201


@pytest.mark.parametrize("name", ["王小明3", "user_01", "李", "!!"])
def test_name_rejects_digits_and_symbols(client, name):
    response = register(client, name=name)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("password", ["Ab1", "gpu2026share", "Gpushareonly", "password123"])
def test_password_must_be_six_chars_with_upper_and_digit(client, password):
    """太短、沒有大寫、沒有數字或過於常見的密碼都會被擋下。"""
    response = register(client, password=password)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_six_character_password_is_accepted(client):
    assert register(client, password="Gpu26x").status_code == 201


def test_register_accepts_optional_email(client):
    assert register(client, email="Student@scu.edu.tw").status_code == 201

    assert User.objects.get(student_id="11172001").email == "Student@scu.edu.tw".lower()


def test_register_rejects_duplicate_email(client):
    register(client, email="student@scu.edu.tw")

    response = register(client, student_id="11172002", email="student@scu.edu.tw")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_register_can_be_closed(settings, client):
    settings.REGISTRATION_OPEN = False

    response = register(client)

    assert response.status_code == 403 and response.json()["code"] == "REGISTRATION_CLOSED"


def test_approval_mode_creates_inactive_account(settings, client):
    settings.REGISTRATION_REQUIRE_APPROVAL = True

    created = register(client)
    assert created.status_code == 201 and created.json()["status"] == "pending"
    assert User.objects.get(student_id="11172001").is_active is False

    login = client.post(
        "/api/auth/login", {"student_id": "11172001", "password": PASSWORD},
        content_type="application/json",
    )
    assert login.status_code == 403 and login.json()["code"] == "ACCOUNT_INACTIVE"


def test_login_accepts_student_id_in_any_format(client):
    register(client, student_id="11172099")
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login", {"student_id": " 1117-2099 ", "password": PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == 200 and response.json()["student_id"] == "11172099"


def test_registration_is_throttled_per_address(client):
    statuses = [
        register(client, student_id=f"1117200{index}").status_code for index in range(1, 8)
    ]

    assert 429 not in statuses[:5]
    assert statuses[-1] == 429


def test_invite_code_creates_an_admin_account(settings, client):
    settings.ADMIN_INVITE_CODE = "team-invite-2026"

    response = register(client, invite_code="team-invite-2026")

    assert response.status_code == 201 and response.json()["is_admin"] is True
    user = User.objects.get(student_id="11172001")
    assert user.is_staff and user.is_superuser and user.is_active


def test_invite_code_bypasses_approval(settings, client):
    settings.ADMIN_INVITE_CODE = "team-invite-2026"
    settings.REGISTRATION_REQUIRE_APPROVAL = True

    assert register(client, invite_code="team-invite-2026").status_code == 201
    assert User.objects.get(student_id="11172001").is_active is True


def test_wrong_invite_code_is_rejected(settings, client):
    settings.ADMIN_INVITE_CODE = "team-invite-2026"

    response = register(client, invite_code="guess")

    assert response.status_code == 403 and response.json()["code"] == "INVITE_CODE_INVALID"
    assert not User.objects.filter(student_id="11172001").exists()


def test_invite_code_is_off_when_unset(settings, client):
    settings.ADMIN_INVITE_CODE = ""

    response = register(client, invite_code="anything")

    assert response.status_code == 403 and response.json()["code"] == "INVITE_CODE_INVALID"


def test_registration_without_invite_code_is_not_admin(client):
    assert register(client).json()["is_admin"] is False
