"""對照 README §4.3 路由表與 §4.4 錯誤格式的契約測試。"""

import json

import pytest
from django.core.cache import cache
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import resolve

from core.exceptions import api_server_error
from core.models import User

SAMPLE_UUID = "00000000-0000-0000-0000-000000000000"

CONTRACT_ROUTES = [
    ("GET", "/api/health"),
    ("GET", "/api/state"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/password"),
    ("POST", "/api/batches"),
    ("GET", f"/api/batches/{SAMPLE_UUID}/download"),
    ("POST", f"/api/jobs/{SAMPLE_UUID}/cancel"),
    ("POST", f"/api/jobs/{SAMPLE_UUID}/retry"),
    ("GET", f"/api/jobs/{SAMPLE_UUID}/input"),
    ("GET", f"/api/artifacts/{SAMPLE_UUID}"),
    ("POST", "/api/pairing-codes"),
    ("PATCH", f"/api/nodes/{SAMPLE_UUID}"),
    ("POST", "/api/agent/pair"),
    ("POST", "/api/agent/heartbeat"),
    ("POST", "/api/agent/claim"),
    ("GET", f"/api/agent/attempts/{SAMPLE_UUID}/input"),
    ("POST", f"/api/agent/attempts/{SAMPLE_UUID}/complete"),
    ("POST", f"/api/agent/attempts/{SAMPLE_UUID}/fail"),
    ("POST", "/api/ai/assist"),
]


@pytest.mark.parametrize(("method", "path"), CONTRACT_ROUTES)
def test_contract_route_registered(method, path):
    view_class = resolve(path).func.view_class
    assert hasattr(view_class, method.lower())


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/state", "/api/auth/me", "/api/batches"])
def test_user_routes_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200 and response.json()["status"] == "ok"


@pytest.mark.django_db
def test_unmatched_api_path_returns_json_404(client):
    response = client.get("/api/jobs/not-a-uuid/cancel")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_server_error_returns_json_for_api_paths():
    response = api_server_error(RequestFactory().get("/api/state"))
    assert response.status_code == 500
    assert json.loads(response.content)["code"] == "SERVER_ERROR"


@pytest.mark.django_db
def test_login_and_logout(client, make_user):
    user = make_user(email="login@scu.edu.tw")
    user.set_password("correct-horse-battery")
    user.save(update_fields=["password"])

    bad = client.post(
        "/api/auth/login", {"email": user.email, "password": "wrong"}, content_type="application/json",
    )
    assert bad.status_code == 403 and bad.json()["code"] == "LOGIN_FAILED"

    good = client.post(
        "/api/auth/login", {"email": user.email, "password": "correct-horse-battery"},
        content_type="application/json",
    )
    assert good.status_code == 200 and good.json()["email"] == user.email
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 403


@pytest.mark.django_db
def test_login_is_throttled_per_account(client):
    cache.clear()
    payload = {"email": "tester@scu.edu.tw", "password": "wrong-password"}
    statuses = [
        client.post("/api/auth/login", payload, content_type="application/json").status_code
        for _ in range(11)
    ]
    assert 429 not in statuses[:10]
    assert statuses[10] == 429


@pytest.mark.django_db
def test_user_role_is_required():
    with pytest.raises(IntegrityError):
        User.objects.create_user(
            username="norole@scu.edu.tw", email="norole@scu.edu.tw", name="無身分", password="unused",
        )
