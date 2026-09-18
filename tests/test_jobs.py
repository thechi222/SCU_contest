"""使用者流程的測試:上傳批次、查看狀態、取消與下載(README §4.3)。"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Job

pytestmark = pytest.mark.django_db


def upload(client, kind="asr", count=1, size=32):
    files = [SimpleUploadedFile(f"sample-{index}.wav", b"x" * size) for index in range(count)]
    return client.post("/api/batches", {"kind": kind, "name": "測試批次", "files": files})


def test_upload_creates_one_job_per_file(client, user):
    client.force_login(user)

    response = upload(client, count=3)

    assert response.status_code == 201
    assert len(response.json()["jobs"]) == 3
    assert Job.objects.filter(status=Job.Status.QUEUED).count() == 3


def test_upload_rejects_too_many_files(settings, client, user):
    settings.MAX_BATCH_FILES = 2
    client.force_login(user)

    response = upload(client, count=3)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_upload_rejects_oversized_file(settings, client, user):
    settings.MAX_FILE_BYTES = 8
    client.force_login(user)

    response = upload(client, size=64)

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_upload_respects_daily_limit(client, make_user):
    limited = make_user(email="quota@scu.edu.tw", daily_limit=1)
    client.force_login(limited)

    assert upload(client, count=1).status_code == 201
    blocked = upload(client, count=1)
    assert blocked.status_code == 429 and blocked.json()["code"] == "QUOTA_EXCEEDED"


def test_state_lists_own_batches_and_limits(client, user, node):
    client.force_login(user)
    upload(client, count=2)

    state = client.get("/api/state").json()

    assert state["user"]["email"] == user.email
    assert len(state["batches"]) == 1 and len(state["batches"][0]["jobs"]) == 2
    assert state["limits"]["kinds"] == ["asr", "upscale"]
    assert len(state["nodes"]) == 1 and state["nodes"][0]["is_mine"] is False


def test_cancel_and_retry_own_job(client, user, make_job):
    job = make_job(user)
    client.force_login(user)

    assert client.post(f"/api/jobs/{job.id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/jobs/{job.id}/retry").json()["status"] == "queued"


def test_cannot_touch_other_users_job(client, make_user, make_job):
    job = make_job(make_user(email="owner@scu.edu.tw"))
    client.force_login(make_user(email="other@scu.edu.tw"))

    for path in (f"/api/jobs/{job.id}/cancel", f"/api/jobs/{job.id}/retry"):
        response = client.post(path)
        assert response.status_code == 404 and response.json()["code"] == "NOT_FOUND"

    assert client.get(f"/api/jobs/{job.id}/input").status_code == 404


def test_owner_can_toggle_sharing_but_others_cannot(client, node, make_user):
    client.force_login(node.owner)
    assert client.patch(
        f"/api/nodes/{node.id}", {"sharing": True}, content_type="application/json",
    ).json()["sharing"] is True

    client.force_login(make_user(email="stranger@scu.edu.tw"))
    response = client.patch(
        f"/api/nodes/{node.id}", {"sharing": False}, content_type="application/json",
    )
    assert response.status_code == 404
