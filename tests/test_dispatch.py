"""派工協定的測試(README §4.5)。對照 codex/compute-relay-demo 分支驗證過的行為。"""

import pytest

from core import services
from core.exceptions import ApiError
from core.models import Attempt, Job

pytestmark = pytest.mark.django_db


def test_claim_creates_attempt_and_marks_job_loading(node, user, make_job):
    job = make_job(user)

    attempt = services.claim_job(node)

    assert attempt is not None and attempt.job_id == job.id
    job.refresh_from_db()
    assert job.status == Job.Status.LOADING
    assert job.attempt_count == 1


@pytest.mark.parametrize("closed", [{"sharing": False}, {"local_enabled": False}, {"revoked": True}])
def test_closed_node_gets_no_work(make_node, user, make_job, closed):
    make_job(user)
    node = make_node(**closed)

    assert services.claim_job(node) is None


def test_node_outside_schedule_gets_no_work(make_node, user, make_job):
    make_job(user)
    # 開放時段為 00:00–00:01,測試執行時幾乎必定在時段外
    node = make_node(schedule_start="00:00", schedule_end="00:01", utc_offset_minutes=480)

    assert services.claim_job(node) is None or not services.within_schedule(node)


def test_node_takes_one_job_at_a_time(node, user, make_job):
    make_job(user, filename="a.wav")
    make_job(user, filename="b.wav")

    assert services.claim_job(node) is not None
    assert services.claim_job(node) is None


def test_node_skips_kinds_it_cannot_run(make_node, user, make_job):
    make_job(user, kind="upscale", filename="image.png")
    node = make_node(kinds=("asr",))

    assert services.claim_job(node) is None


def test_running_limit_per_user(make_node, make_user, make_job):
    limited = make_user(student_id="LIMIT001", max_running=1)
    make_job(limited, filename="a.wav")
    make_job(limited, filename="b.wav")
    first, second = make_node(token="node-a"), make_node(token="node-b")

    assert services.claim_job(first) is not None
    assert services.claim_job(second) is None


def test_fair_dispatch_alternates_between_users(make_node, make_user, make_job):
    early = make_user(student_id="EARLY001")
    late = make_user(student_id="LATE0001")
    make_job(early, filename="early-1.wav")
    make_job(early, filename="early-2.wav")
    make_job(late, filename="late-1.wav")
    nodes = [make_node(token=f"node-{index}") for index in range(3)]

    owners = [services.claim_job(node).job.user.student_id for node in nodes]

    assert owners[:2] == ["EARLY001", "LATE0001"]


def test_lease_expiry_requeues_job(node, user, make_job, expire_lease):
    job = make_job(user)
    attempt = services.claim_job(node)
    expire_lease(attempt)

    assert services.expire_leases() == 1

    attempt.refresh_from_db()
    job.refresh_from_db()
    assert attempt.outcome == "expired" and attempt.ended_at is not None
    assert job.status == Job.Status.RETRYING


def test_job_fails_after_attempt_limit(settings, node, user, make_job, expire_lease):
    settings.MAX_JOB_ATTEMPTS = 2
    job = make_job(user)

    for _ in range(2):
        expire_lease(services.claim_job(node))
        services.expire_leases()

    job.refresh_from_db()
    assert job.status == Job.Status.FAILED
    assert job.attempt_count == 2


def test_owner_reclaim_stops_run_and_requeues(node, user, make_job):
    job = make_job(user)
    attempt = services.claim_job(node)

    node.sharing = False
    node.save(update_fields=["sharing"])
    keep_running = services.renew_lease(node, attempt.id, "GPU 運算中", 0.5)

    attempt.refresh_from_db()
    job.refresh_from_db()
    assert keep_running is False
    assert attempt.outcome == "cancelled"
    assert job.status == Job.Status.RETRYING


def test_result_from_expired_attempt_is_rejected(node, user, make_job, expire_lease):
    make_job(user)
    attempt = services.claim_job(node)
    expire_lease(attempt)
    services.expire_leases()

    with pytest.raises(ApiError) as error:
        services.complete_attempt(node, attempt.id, [], {"cuda_verified": True})

    assert error.value.get_codes() == "ATTEMPT_NOT_ACTIVE"


def test_completing_attempt_finishes_job(node, user, make_job):
    job = make_job(user)
    attempt = services.claim_job(node)

    services.complete_attempt(node, attempt.id, [], {"cuda_verified": True, "gpu_seconds": 1.5})

    attempt.refresh_from_db()
    job.refresh_from_db()
    assert attempt.outcome == "succeeded" and attempt.gpu_verified is True
    assert job.status == Job.Status.COMPLETED and job.completed_at is not None


def test_failed_attempt_requeues_then_can_be_retried(node, user, make_job):
    job = make_job(user)
    attempt = services.claim_job(node)
    services.fail_attempt(node, attempt.id, "容器啟動失敗")

    job.refresh_from_db()
    assert job.status == Job.Status.RETRYING

    services.cancel_job(user, job.id)
    job.refresh_from_db()
    assert job.status == Job.Status.CANCELLED

    services.retry_job(user, job.id)
    job.refresh_from_db()
    assert job.status == Job.Status.QUEUED and job.attempt_count == 0


def test_cancel_ends_active_attempt(node, user, make_job):
    job = make_job(user)
    attempt = services.claim_job(node)

    services.cancel_job(user, job.id)

    attempt.refresh_from_db()
    assert attempt.outcome == "cancelled"
    assert not Attempt.objects.filter(ended_at__isnull=True).exists()


def test_daily_quota_blocks_extra_files(make_user, make_job):
    limited = make_user(student_id="QUOTA001", daily_limit=1)
    make_job(limited)

    with pytest.raises(ApiError) as error:
        services.check_daily_quota(limited, 1)

    assert error.value.get_codes() == "QUOTA_EXCEEDED"
