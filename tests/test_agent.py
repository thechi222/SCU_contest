"""Agent token 與任務通道的契約測試(README §4.3、§4.6)。"""

import io

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.authentication import hash_agent_token
from core.models import Machine

TOKEN = "token-for-lab-gpu-01"


@pytest.fixture
def machines(db):
    lab = Machine.objects.create(
        id="lab-gpu-01", name="lab", cpu_model="cpu", ram_gb=16, owner_dept="dept",
        agent_token_hash=hash_agent_token(TOKEN),
    )
    laptop = Machine.objects.create(
        id="team-laptop-01", name="laptop", cpu_model="cpu", ram_gb=16, owner_dept="dept",
    )
    return lab, laptop


def send_heartbeat(client, machine_id, token=None):
    headers = {"X-Agent-Token": token} if token else {}
    payload = {
        "machine_id": machine_id, "cpu_percent": 12.5, "ram_percent": 40.0,
        "timestamp": timezone.now().isoformat(),
    }
    return client.post("/api/agent/heartbeat", payload, content_type="application/json", headers=headers)


def test_agent_routes_require_token(client, machines):
    response = send_heartbeat(client, "lab-gpu-01")
    assert response.status_code == 403
    assert response.json()["code"] == "NOT_AUTHENTICATED"


def test_agent_rejects_unknown_token(client, machines):
    response = send_heartbeat(client, "lab-gpu-01", token="wrong-token")
    assert response.status_code == 403
    assert response.json()["code"] == "AUTHENTICATION_FAILED"


def test_agent_token_is_bound_to_its_machine(client, machines):
    response = send_heartbeat(client, "team-laptop-01", token=TOKEN)
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


@pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="待 §6.1 實作;完成後移除此標記")
def test_heartbeat_accepted_for_own_machine(client, machines):
    response = send_heartbeat(client, "lab-gpu-01", token=TOKEN)
    assert response.status_code == 200
    assert Machine.objects.get(id="lab-gpu-01").heartbeats.count() == 1


def test_issue_agent_token_replaces_previous_token(client, machines):
    out = io.StringIO()
    call_command("issue_agent_token", "lab-gpu-01", stdout=out)
    new_token = out.getvalue().split()[-1]

    assert Machine.objects.get(id="lab-gpu-01").agent_token_hash == hash_agent_token(new_token)
    assert send_heartbeat(client, "lab-gpu-01", token=TOKEN).json()["code"] == "AUTHENTICATION_FAILED"
