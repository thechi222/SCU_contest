"""Agent 配對與任務通道的端到端測試(README §4.3、§4.6)。"""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core import rentals
from core.models import Artifact, Job, Node, Rental, UsageSample
from core.profiles import PROFILES

pytestmark = pytest.mark.django_db

CAPABILITIES = {"asr": {"profile": PROFILES["asr"], "cuda_verified": True, "peak_vram_mb": 2048}}


def pair_payload(**overrides):
    return {
        "code": overrides.pop("code", ""), "name": "我的 RTX 3050",
        "gpu_uuid": "GPU-test-0001", "gpu_name": "NVIDIA RTX 3050",
        "memory_mb": 8192, "capabilities": CAPABILITIES,
        "environment": {"driver": "560.00", "os": "Windows"}, **overrides,
    }


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def paired(client, user):
    """走完一次配對:取得配對碼並登錄節點。"""
    client.force_login(user)
    code = client.post("/api/pairing-codes").json()["code"]
    client.logout()

    response = client.post(
        "/api/agent/pair", pair_payload(code=code), content_type="application/json",
    )
    assert response.status_code == 200
    return response.json()["token"]


def test_pairing_code_registers_node(paired, user):
    node = Node.objects.get(gpu_uuid="GPU-test-0001")
    assert node.owner == user
    assert node.capabilities == CAPABILITIES
    assert node.sharing is False   # 配對後仍須由機主開啟分享


def test_pairing_code_is_single_use(client, user):
    client.force_login(user)
    code = client.post("/api/pairing-codes").json()["code"]
    client.logout()

    first = client.post("/api/agent/pair", pair_payload(code=code), content_type="application/json")
    second = client.post(
        "/api/agent/pair", pair_payload(code=code, gpu_uuid="GPU-test-0002"),
        content_type="application/json",
    )

    assert first.status_code == 200
    assert second.status_code == 403 and second.json()["code"] == "PAIRING_CODE_INVALID"


def test_pairing_rejects_untested_gpu(client, user):
    client.force_login(user)
    code = client.post("/api/pairing-codes").json()["code"]
    client.logout()
    payload = pair_payload(code=code, capabilities={"asr": {"profile": PROFILES["asr"], "cuda_verified": False, "peak_vram_mb": 2048}})

    response = client.post("/api/agent/pair", payload, content_type="application/json")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_agent_endpoints_require_token(client):
    response = client.post("/api/agent/claim")
    assert response.status_code == 403 and response.json()["code"] == "NOT_AUTHENTICATED"


def test_agent_rejects_unknown_token(client):
    response = client.post("/api/agent/claim", headers=bearer("wrong-token"))
    assert response.status_code == 403 and response.json()["code"] == "AUTHENTICATION_FAILED"


def test_heartbeat_reports_sharing_and_schedule(client, paired):
    body = {"local_enabled": True, "capabilities": CAPABILITIES, "telemetry": {"gpu_utilization": 12}}

    response = client.post(
        "/api/agent/heartbeat", body, content_type="application/json", headers=bearer(paired),
    )

    assert response.status_code == 200
    assert response.json() == {
        "stop": False, "lease_seconds": 20.0, "sharing": False, "within_schedule": True,
    }
    node = Node.objects.get(gpu_uuid="GPU-test-0001")
    assert node.local_enabled is True and node.telemetry == {"gpu_utilization": 12}


def test_claim_returns_nothing_until_owner_shares(client, paired, user, make_job):
    make_job(user)

    assert client.post("/api/agent/claim", headers=bearer(paired)).json()["assignment"] is None

    Node.objects.update(sharing=True, local_enabled=True)
    assignment = client.post("/api/agent/claim", headers=bearer(paired)).json()["assignment"]
    assert assignment["kind"] == "asr"
    assert assignment["input_url"] == f"/api/agent/attempts/{assignment['attempt_id']}/input"


def test_agent_runs_job_end_to_end(client, paired, user, make_job):
    job = make_job(user)
    Node.objects.update(sharing=True, local_enabled=True)
    assignment = client.post("/api/agent/claim", headers=bearer(paired)).json()["assignment"]

    download = client.get(assignment["input_url"], headers=bearer(paired))
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == b"input-bytes"

    response = client.post(
        f"/api/agent/attempts/{assignment['attempt_id']}/complete",
        {
            "files": [
                SimpleUploadedFile("transcript.txt", "逐字稿".encode()),
                SimpleUploadedFile("subtitles.srt", b"1\n00:00:00,000 --> 00:00:01,000\n"),
            ],
            "metrics": json.dumps({"cuda_verified": True, "gpu_seconds": 2.5}),
        },
        headers=bearer(paired),
    )

    assert response.status_code == 200
    job.refresh_from_db()
    assert job.status == Job.Status.COMPLETED
    assert sorted(Artifact.objects.values_list("name", flat=True)) == ["subtitles.srt", "transcript.txt"]


def test_complete_rejects_unexpected_artifacts(client, paired, user, make_job):
    make_job(user)
    Node.objects.update(sharing=True, local_enabled=True)
    assignment = client.post("/api/agent/claim", headers=bearer(paired)).json()["assignment"]

    response = client.post(
        f"/api/agent/attempts/{assignment['attempt_id']}/complete",
        {"files": [SimpleUploadedFile("something-else.txt", b"x")], "metrics": "{}"},
        headers=bearer(paired),
    )

    assert response.status_code == 400 and response.json()["code"] == "ARTIFACT_MISMATCH"


def test_revoked_node_loses_access(client, paired):
    Node.objects.update(revoked=True)

    response = client.post("/api/agent/claim", headers=bearer(paired))

    assert response.status_code == 403 and response.json()["code"] == "AUTHENTICATION_FAILED"


def test_heartbeat_stores_a_usage_sample(client, paired):
    body = {"local_enabled": True, "telemetry": {"gpu_utilization": 33, "memory_used_mb": 1024}}

    client.post("/api/agent/heartbeat", body, content_type="application/json", headers=bearer(paired))

    sample = UsageSample.objects.get()
    assert (sample.gpu_utilization, sample.memory_used_mb) == (33.0, 1024)


def test_agent_rental_channel_end_to_end(client, paired, user):
    """租借的機台通道:領取 → 回報可連線 → 心跳續約 → 回報容器停止(§4.10)。"""
    Node.objects.update(sharing=True, local_enabled=True, allow_rental=True)
    rentals.request_rental(user, "pytorch", 30, "測試")

    assignment = client.post("/api/agent/rentals/claim", headers=bearer(paired)).json()["rental"]
    assert assignment["image"].startswith("powershare/workspace-pytorch")

    ready = client.post(
        f"/api/agent/rentals/{assignment['rental_id']}/ready",
        {"connect_url": "https://tunnel.example/lab", "connect_token": "abc",
         "connection": {"tunnel": "測試通道"}},
        content_type="application/json", headers=bearer(paired),
    )
    assert ready.status_code == 200

    beat = client.post(
        "/api/agent/heartbeat", {"local_enabled": True, "rental_id": assignment["rental_id"]},
        content_type="application/json", headers=bearer(paired),
    ).json()
    assert beat["stop"] is False

    ended = client.post(
        f"/api/agent/rentals/{assignment['rental_id']}/ended", {"reason": "使用者關閉"},
        content_type="application/json", headers=bearer(paired),
    )
    assert ended.status_code == 200
    assert Rental.objects.get().status == Rental.Status.ENDED


def test_agent_claim_returns_null_when_node_does_not_accept_rentals(client, paired, user):
    Node.objects.update(sharing=True, local_enabled=True, allow_rental=False)
    rentals.request_rental(user, "pytorch", 30, "測試")

    assert client.post("/api/agent/rentals/claim", headers=bearer(paired)).json()["rental"] is None
