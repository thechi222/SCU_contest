"""對照 README §4.2 路由表的基本契約測試。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402

CONTRACT_ROUTES = {
    ("GET", "/api/machines"),
    ("POST", "/api/bookings"),
    ("GET", "/api/bookings/{booking_id}"),
    ("POST", "/api/bookings/{booking_id}/cancel"),
    ("GET", "/api/bookings/{booking_id}/report"),
    ("POST", "/api/agent/heartbeat"),
    ("POST", "/api/ai/assist"),
}


def test_contract_routes_registered():
    registered = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert CONTRACT_ROUTES <= registered
