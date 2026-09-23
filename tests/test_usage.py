"""閒置算力儀表板的取樣、彙整與匯出測試(README §4.9)。"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core import usage
from core.models import Attempt, NodeDailyUsage, UsageSample

pytestmark = pytest.mark.django_db


@pytest.fixture
def online_node(node):
    node.last_seen = timezone.now()
    node.telemetry = {"gpu_utilization": 40, "memory_used_mb": 2048, "temperature_c": 61, "power_w": 120}
    node.save(update_fields=["last_seen", "telemetry"])
    return node


def age_samples(seconds):
    UsageSample.objects.update(captured_at=timezone.now() - timedelta(seconds=seconds))


def test_sample_is_throttled_per_node(settings, online_node):
    assert usage.record_sample(online_node) is not None
    assert usage.record_sample(online_node) is None          # 未達取樣間隔

    age_samples(settings.USAGE_SAMPLE_SECONDS + 1)
    assert usage.record_sample(online_node) is not None
    assert UsageSample.objects.count() == 2


def test_sample_records_telemetry_and_idle_state(online_node):
    sample = usage.record_sample(online_node)

    assert sample.state == UsageSample.State.IDLE
    assert (sample.gpu_utilization, sample.memory_used_mb) == (40.0, 2048)
    assert sample.busy_seconds == 0


def test_busy_state_counts_towards_busy_seconds(settings, online_node, user, make_job):
    job = make_job(user)
    Attempt.objects.create(job=job, node=online_node, lease_until=timezone.now() + timedelta(seconds=20))

    sample = usage.record_sample(online_node)

    assert sample.state == UsageSample.State.BUSY
    assert sample.busy_seconds == settings.USAGE_SAMPLE_SECONDS


def test_offline_node_is_recorded_as_offline(settings, online_node):
    online_node.last_seen = timezone.now() - timedelta(seconds=settings.NODE_OFFLINE_SECONDS + 5)
    online_node.save(update_fields=["last_seen"])

    assert usage.record_sample(online_node).state == UsageSample.State.OFFLINE


def test_roll_up_writes_daily_totals(settings, online_node, user, make_job):
    job = make_job(user)
    attempt = Attempt.objects.create(
        job=job, node=online_node, lease_until=timezone.now() + timedelta(seconds=20),
    )
    usage.record_sample(online_node)                          # 執行中
    age_samples(settings.USAGE_SAMPLE_SECONDS + 1)
    attempt.ended_at = timezone.now()
    attempt.outcome = "succeeded"
    attempt.metrics = {"gpu_seconds": 12.5}
    attempt.save(update_fields=["ended_at", "outcome", "metrics"])
    usage.record_sample(online_node)                          # 閒置

    assert usage.roll_up() == 1

    row = NodeDailyUsage.objects.get(node=online_node, day=timezone.localdate())
    assert row.busy_seconds == settings.USAGE_SAMPLE_SECONDS
    assert row.jobs_completed == 1 and row.gpu_seconds == 12.5
    assert row.avg_utilization == 40.0


def test_roll_up_is_repeatable(online_node):
    usage.record_sample(online_node)
    usage.roll_up()
    usage.roll_up()

    assert NodeDailyUsage.objects.count() == 1


def test_prune_removes_expired_samples_but_keeps_daily_rows(settings, online_node):
    usage.record_sample(online_node)
    usage.roll_up()
    age_samples(settings.USAGE_RETENTION_DAYS * 86400 + 60)

    assert usage.prune_samples() == 1
    assert UsageSample.objects.count() == 0
    assert NodeDailyUsage.objects.count() == 1


def test_summary_endpoint_returns_totals_and_nodes(client, online_node):
    client.force_login(online_node.owner)
    usage.record_sample(online_node)

    body = client.get("/api/usage/summary").json()

    assert body["totals"]["nodes_online"] == 1
    assert body["totals"]["nodes_idle"] == 1
    assert body["nodes"][0]["state"] == UsageSample.State.IDLE
    assert body["nodes"][0]["is_mine"] is True
    assert len(body["nodes"][0]["series"]) == 1


def test_summary_requires_login(client):
    assert client.get("/api/usage/summary").json()["code"] == "NOT_AUTHENTICATED"


def test_export_returns_csv(client, online_node):
    client.force_login(online_node.owner)
    usage.record_sample(online_node)
    usage.roll_up()

    response = client.get("/api/usage/export?days=7")
    content = b"".join(response.streaming_content).decode("utf-8")

    assert response["Content-Type"].startswith("text/csv")
    assert content.splitlines()[0].startswith("day,node,gpu")
    assert online_node.name in content


def test_export_rejects_invalid_range(client, online_node):
    client.force_login(online_node.owner)

    response = client.get("/api/usage/export?days=0")

    assert response.status_code == 400 and response.json()["code"] == "VALIDATION_ERROR"
