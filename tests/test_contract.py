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
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/machines"),
    ("GET", "/api/machines/lab-gpu-01/availability"),
    ("GET", "/api/machines/lab-gpu-01/metrics"),
    ("GET", "/api/bookings"),
    ("POST", "/api/bookings"),
    ("GET", f"/api/bookings/{SAMPLE_UUID}"),
    ("POST", f"/api/bookings/{SAMPLE_UUID}/cancel"),
    ("GET", f"/api/bookings/{SAMPLE_UUID}/report"),
    ("POST", "/api/agent/heartbeat"),
    ("POST", "/api/agent/tasks/claim"),
    ("POST", f"/api/agent/tasks/{SAMPLE_UUID}/result"),
    ("POST", "/api/ai/assist"),
]


@pytest.mark.parametrize(("method", "path"), CONTRACT_ROUTES)
def test_contract_route_registered(method, path):
    view_class = resolve(path).func.view_class
    assert hasattr(view_class, method.lower())


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/auth/me", "/api/machines", "/api/bookings"])
def test_user_routes_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_unmatched_api_path_returns_json_404(client):
    response = client.get("/api/bookings/not-a-uuid")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_server_error_returns_json_for_api_paths():
    response = api_server_error(RequestFactory().get("/api/machines"))
    assert response.status_code == 500
    assert json.loads(response.content)["code"] == "SERVER_ERROR"


@pytest.mark.django_db
def test_login_is_throttled_per_account(client):
    cache.clear()
    client.raise_request_exception = False
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
            username="norole@scu.edu.tw", email="norole@scu.edu.tw", name="無身分", password="unused-password",
        )
