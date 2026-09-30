"""互動式租借的流程測試(README §4.10)。"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core import rentals, services
from core.exceptions import ApiError
from core.models import Rental

pytestmark = pytest.mark.django_db


@pytest.fixture
def rental_node(make_node):
    return make_node(allow_rental=True)


def make_rental(user, minutes=60, workspace="asr"):
    return rentals.request_rental(user, workspace, minutes, "專題實驗")


def test_request_creates_queued_rental(user):
    rental = make_rental(user)

    assert rental.status == Rental.Status.QUEUED
    assert rental.image.startswith("powershare/workspace-asr")


def test_one_open_rental_per_user(user):
    make_rental(user)

    with pytest.raises(ApiError) as error:
        make_rental(user)
    assert error.value.get_codes() == "RENTAL_ALREADY_OPEN"


def test_daily_minutes_are_limited(settings, user):
    settings.RENTAL_DAILY_MINUTES = 60
    rental = make_rental(user, minutes=60)
    rentals.finish(rental, Rental.Status.ENDED, "測試結束")

    with pytest.raises(ApiError) as error:
        make_rental(user, minutes=30)
    assert error.value.get_codes() == "QUOTA_EXCEEDED"


def test_node_must_opt_in_before_receiving_rentals(make_node, user):
    plain = make_node(token="plain-node-token")
    make_rental(user)

    assert rentals.claim_rental(plain) is None


def test_claim_then_ready_starts_the_clock(rental_node, user):
    make_rental(user, minutes=30)

    claimed = rentals.claim_rental(rental_node)
    assert claimed.status == Rental.Status.STARTING

    ready = rentals.mark_ready(
        rental_node, claimed.id, "https://tunnel.example/lab", "token-abc", {"tunnel": "測試"},
    )
    assert ready.status == Rental.Status.ACTIVE
    assert ready.expires_at - ready.started_at >= timedelta(minutes=29)


def test_rental_blocks_job_dispatch_on_that_node(rental_node, user, make_job):
    make_job(user)
    make_rental(user)
    rentals.mark_ready(
        rental_node, rentals.claim_rental(rental_node).id, "https://tunnel.example/lab", "t", {},
    )

    assert services.claim_job(rental_node) is None


def test_running_job_blocks_rental_claim(rental_node, user, make_job):
    make_job(user)
    services.claim_job(rental_node)
    make_rental(user)

    assert rentals.claim_rental(rental_node) is None


def test_renew_stops_when_owner_withdraws_the_node(rental_node, user):
    make_rental(user)
    rental = rentals.mark_ready(
        rental_node, rentals.claim_rental(rental_node).id, "https://tunnel.example/lab", "t", {},
    )
    rental_node.sharing = False
    rental_node.save(update_fields=["sharing"])

    assert rentals.renew_lease(rental_node, rental.id) is False
    rental.refresh_from_db()
    assert rental.status == Rental.Status.ENDED and rental.connect_token == ""


def test_expired_rental_is_closed_by_the_scheduler(rental_node, user):
    make_rental(user, minutes=10)
    rental = rentals.mark_ready(
        rental_node, rentals.claim_rental(rental_node).id, "https://tunnel.example/lab", "t", {},
    )
    rental.expires_at = timezone.now() - timedelta(seconds=1)
    rental.save(update_fields=["expires_at"])

    assert rentals.expire_rentals() == 1
    rental.refresh_from_db()
    assert rental.status == Rental.Status.EXPIRED


def test_lost_node_during_startup_requeues_the_rental(rental_node, user):
    make_rental(user)
    rental = rentals.claim_rental(rental_node)
    rental.lease_until = timezone.now() - timedelta(seconds=1)
    rental.save(update_fields=["lease_until"])

    assert rentals.expire_rentals() == 1
    rental.refresh_from_db()
    assert rental.status == Rental.Status.QUEUED and rental.node is None


def test_cancel_marks_active_rental_as_ending(rental_node, user):
    make_rental(user)
    rental = rentals.mark_ready(
        rental_node, rentals.claim_rental(rental_node).id, "https://tunnel.example/lab", "t", {},
    )

    cancelled = rentals.cancel_rental(user, rental.id)

    assert cancelled.status == Rental.Status.ENDING and cancelled.connect_token == ""


def test_agent_reports_container_stopped(rental_node, user):
    make_rental(user)
    rental = rentals.mark_ready(
        rental_node, rentals.claim_rental(rental_node).id, "https://tunnel.example/lab", "t", {},
    )

    ended = rentals.agent_ended(rental_node, rental.id, "使用者關閉")

    assert ended.status == Rental.Status.ENDED and ended.ended_at is not None


def test_rental_endpoints_for_users(client, user):
    client.force_login(user)

    created = client.post(
        "/api/rentals", {"workspace": "asr", "minutes": 30, "purpose": "測試"},
        content_type="application/json",
    )
    assert created.status_code == 201

    listed = client.get("/api/rentals").json()
    assert listed["rentals"][0]["status"] == Rental.Status.QUEUED
    assert listed["limits"]["max_minutes"] > 0

    rental_id = created.json()["id"]
    cancelled = client.post(f"/api/rentals/{rental_id}/cancel")
    assert cancelled.json()["status"] == Rental.Status.CANCELLED


def test_rental_rejects_unknown_workspace(client, user):
    client.force_login(user)

    response = client.post(
        "/api/rentals", {"workspace": "unknown", "minutes": 30}, content_type="application/json",
    )

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"


def test_rental_rejects_environment_that_is_not_built(client, user):
    client.force_login(user)

    response = client.post(
        "/api/rentals", {"workspace": "train", "minutes": 30}, content_type="application/json",
    )

    assert response.status_code == 400 and response.json()["code"] == "ENVIRONMENT_NOT_READY"


def test_node_with_the_environment_ready_is_preferred(make_node, make_user, user):
    """已通過該任務自我測試的機台直接啟動;其他機台要先建置環境。"""
    ready = make_node(token="ready-node", kinds=("asr",), allow_rental=True)
    make_rental(user, workspace="asr")

    claimed = rentals.claim_rental(ready)

    assert claimed.prepared is True and claimed.stage == "啟動容器"


def test_node_without_the_environment_builds_it_first(make_node, user):
    blank = make_node(token="blank-node", kinds=("upscale",), allow_rental=True)
    make_rental(user, workspace="asr")

    claimed = rentals.claim_rental(blank)

    assert claimed.prepared is False and claimed.stage == "建置環境"


def test_heartbeat_reports_build_progress(rental_node, user):
    make_rental(user, workspace="asr")
    rental = rentals.claim_rental(rental_node)

    assert rentals.renew_lease(rental_node, rental.id, "下載模型", 0.4) is True

    rental.refresh_from_db()
    assert rental.stage == "下載模型" and rental.progress == 0.4
