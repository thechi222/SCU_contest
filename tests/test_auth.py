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


def register(client, **overrides):
    payload = {
        "student_id": "11172001", "name": "測試學生", "role": "student",
        "password": "correct-horse-battery", **overrides,
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
    assert register(client, student_id=" a11-172001 ").status_code == 201

    assert User.objects.filter(student_id="A11172001").exists()


def test_register_rejects_duplicate_student_id(client, make_user):
    make_user(student_id="11172001")

    response = register(client)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_register_rejects_malformed_student_id(client):
    response = register(client, student_id="11@7")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_register_rejects_short_password(client):
    response = register(client, password="short")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_register_rejects_common_password(client):
    response = register(client, password="password1234")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


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
        "/api/auth/login", {"student_id": "11172001", "password": "correct-horse-battery"},
        content_type="application/json",
    )
    assert login.status_code == 403 and login.json()["code"] == "ACCOUNT_INACTIVE"


def test_login_accepts_student_id_in_any_format(client):
    register(client, student_id="A11172001")
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login", {"student_id": " a11-172001 ", "password": "correct-horse-battery"},
        content_type="application/json",
    )

    assert response.status_code == 200 and response.json()["student_id"] == "A11172001"


def test_registration_is_throttled_per_address(client):
    statuses = [
        register(client, student_id=f"1117200{index}").status_code for index in range(1, 8)
    ]

    assert 429 not in statuses[:5]
    assert statuses[-1] == 429
