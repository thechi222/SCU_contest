"""對照 README §4.3 路由表與 §4.4 錯誤格式的基本契約測試。"""

import pytest
from django.urls import resolve

SAMPLE_BOOKING_ID = "00000000-0000-0000-0000-000000000000"

CONTRACT_ROUTES = [
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("GET", "/api/machines"),
    ("GET", "/api/machines/lab-gpu-01/metrics"),
    ("GET", "/api/bookings"),
    ("POST", "/api/bookings"),
    ("GET", f"/api/bookings/{SAMPLE_BOOKING_ID}"),
    ("POST", f"/api/bookings/{SAMPLE_BOOKING_ID}/cancel"),
    ("GET", f"/api/bookings/{SAMPLE_BOOKING_ID}/report"),
    ("POST", "/api/agent/heartbeat"),
    ("POST", "/api/ai/assist"),
]


@pytest.mark.parametrize(("method", "path"), CONTRACT_ROUTES)
def test_contract_route_registered(method, path):
    view_class = resolve(path).func.view_class
    assert hasattr(view_class, method.lower())


@pytest.mark.django_db
def test_login_required_routes_reject_anonymous(client):
    response = client.get("/api/bookings")
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_AUTHENTICATED"


@pytest.mark.django_db
def test_heartbeat_rejects_missing_agent_token(client):
    response = client.post("/api/agent/heartbeat", {}, content_type="application/json")
    assert response.status_code == 403
    assert set(response.json()) == {"detail", "code"}
