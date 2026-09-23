"""派工協定。所有狀態轉換都在交易內完成,並以租約與 attempt 識別避免延遲結果覆蓋新狀態。"""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from core.exceptions import ApiError
from core.models import Attempt, Event, Job, Node, Rental


def record(kind: str, message: str, *, user=None, node=None, job=None) -> None:
    Event.objects.create(kind=kind, message=message[:300], user=user, node=node, job=job)


def within_schedule(node: Node, now=None) -> bool:
    """節點設定的每日開放時段;未設定時視為全天開放。"""
    if not node.schedule_start or not node.schedule_end:
        return True
    now = now or timezone.now()
    local = now.astimezone(dt_timezone(timedelta(minutes=node.utc_offset_minutes)))
    current = local.strftime("%H:%M")
    if node.schedule_start <= node.schedule_end:
        return node.schedule_start <= current < node.schedule_end
    return current >= node.schedule_start or current < node.schedule_end   # 跨午夜


def node_accepts_work(node: Node) -> bool:
    return bool(node.sharing and node.local_enabled and not node.revoked and within_schedule(node))


def end_attempt(attempt: Attempt, outcome: str, error: str = "", *, now=None) -> None:
    attempt.ended_at = now or timezone.now()
    attempt.outcome = outcome
    attempt.error = error[:400]
    attempt.save(update_fields=["ended_at", "outcome", "error"])


def requeue_or_fail(job: Job, reason: str) -> None:
    """接力重試:未達上限則重新排隊,達上限標為失敗。"""
    if job.attempt_count >= settings.MAX_JOB_ATTEMPTS:
        job.status = Job.Status.FAILED
        job.error = reason[:400]
        job.completed_at = timezone.now()
        job.stage = "已結束"
    else:
        job.status = Job.Status.RETRYING
        job.error = reason[:400]
        job.stage = "等待可用設備"
        job.progress = None
    job.save(update_fields=["status", "error", "stage", "progress", "completed_at"])
    record("job", f"{job.filename}:{reason}", user=job.user, job=job)


@transaction.atomic
def claim_job(node: Node) -> Attempt | None:
    """為節點取出一件工作並建立 attempt。節點未開放、已有進行中的 attempt 或無合適工作時回傳 None。"""
    node = Node.objects.select_for_update().get(pk=node.pk)
    if not node_accepts_work(node):
        return None
    if Attempt.objects.filter(node=node, ended_at__isnull=True).exists():
        return None
    if Rental.objects.filter(node=node, status__in=Rental.ON_NODE).exists():
        return None   # 互動式租借期間整台設備由租借者使用(§4.10)

    kinds = [kind for kind in node.capabilities if node.capabilities[kind].get("cuda_verified")]
    if not kinds:
        return None

    over_limit = [
        row["user"]
        for row in Job.objects.filter(status__in=Job.ACTIVE)
        .values("user", "user__max_running")
        .annotate(running=Count("id"))
        if row["running"] >= row["user__max_running"]
    ]

    job = (
        Job.objects.select_for_update(skip_locked=True)
        .filter(status__in=Job.PENDING, kind__in=kinds)
        .exclude(user_id__in=over_limit)
        .select_related("user")
        .order_by("user__last_dispatch", "created_at")
        .first()
    )
    if job is None:
        return None

    now = timezone.now()
    attempt = Attempt.objects.create(
        job=job, node=node, lease_until=now + timedelta(seconds=settings.LEASE_SECONDS),
    )
    job.status = Job.Status.LOADING
    job.stage = "下載輸入"
    job.attempt_count += 1
    job.progress = None
    job.save(update_fields=["status", "stage", "attempt_count", "progress"])

    next_turn = (Job.objects.aggregate(top=Max("user__last_dispatch"))["top"] or 0) + 1
    type(job.user).objects.filter(pk=job.user_id).update(last_dispatch=next_turn)
    record("dispatch", f"{job.filename} 派給 {node.name}", user=job.user, node=node, job=job)
    return attempt


@transaction.atomic
def renew_lease(node: Node, attempt_id, stage: str | None, progress: float | None) -> bool:
    """續約成功回傳 True;attempt 已結束、節點已關閉分享或不在開放時段時回傳 False,Agent 應立即停止容器。"""
    attempt = (
        Attempt.objects.select_for_update()
        .filter(pk=attempt_id, node=node, ended_at__isnull=True)
        .select_related("job")
        .first()
    )
    if attempt is None:
        return False
    if not node_accepts_work(node):
        end_attempt(attempt, "cancelled", "機主已停止分享")
        requeue_or_fail(attempt.job, "機主收回設備,工作重新排隊")
        return False

    attempt.lease_until = timezone.now() + timedelta(seconds=settings.LEASE_SECONDS)
    attempt.save(update_fields=["lease_until"])

    job = attempt.job
    updates = []
    if stage and job.stage != stage:
        job.stage = stage
        updates.append("stage")
    if job.status != Job.Status.RUNNING and stage in ("GPU 運算中", "上傳結果"):
        job.status = Job.Status.RUNNING
        updates.append("status")
    if progress is not None:
        job.progress = progress
        updates.append("progress")
    if updates:
        job.save(update_fields=updates)
    return True


@transaction.atomic
def complete_attempt(node: Node, attempt_id, artifacts: list, metrics: dict) -> None:
    """只接受仍持有租約的 attempt 回報,避免逾時後的舊結果覆寫重新派工的工作。"""
    attempt = (
        Attempt.objects.select_for_update()
        .filter(pk=attempt_id, node=node, ended_at__isnull=True)
        .select_related("job")
        .first()
    )
    if attempt is None:
        raise ApiError("這次執行已結束,結果不予採用", code="ATTEMPT_NOT_ACTIVE", status_code=409)

    attempt.metrics = metrics
    attempt.gpu_verified = bool(metrics.get("cuda_verified"))
    attempt.save(update_fields=["metrics", "gpu_verified"])
    end_attempt(attempt, "succeeded")

    job = attempt.job
    for artifact in artifacts:
        artifact.job = job
        artifact.save()
    job.status = Job.Status.COMPLETED
    job.stage = "已完成"
    job.progress = 1.0
    job.error = ""
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "stage", "progress", "error", "completed_at"])
    record("job", f"{job.filename} 已完成", user=job.user, node=node, job=job)


@transaction.atomic
def fail_attempt(node: Node, attempt_id, reason: str) -> None:
    attempt = (
        Attempt.objects.select_for_update()
        .filter(pk=attempt_id, node=node, ended_at__isnull=True)
        .select_related("job")
        .first()
    )
    if attempt is None:
        raise ApiError("這次執行已結束", code="ATTEMPT_NOT_ACTIVE", status_code=409)
    end_attempt(attempt, "failed", reason)
    requeue_or_fail(attempt.job, reason)


def expire_leases() -> int:
    """由排程器每秒呼叫。租約逾時代表節點失聯,工作重新排隊。"""
    now = timezone.now()
    expired = list(
        Attempt.objects.filter(ended_at__isnull=True, lease_until__lt=now).select_related("job", "node")
    )
    for attempt in expired:
        with transaction.atomic():
            fresh = Attempt.objects.select_for_update().filter(pk=attempt.pk, ended_at__isnull=True).first()
            if fresh is None:
                continue
            end_attempt(fresh, "expired", "租約逾時")
            requeue_or_fail(attempt.job, "設備失去聯繫,工作重新排隊")
    return len(expired)


def mark_offline_nodes() -> int:
    """心跳中斷的節點不再視為線上;進行中的工作由租約逾時處理。"""
    deadline = timezone.now() - timedelta(seconds=settings.NODE_OFFLINE_SECONDS)
    return Node.objects.filter(
        Q(last_seen__lt=deadline) | Q(last_seen__isnull=True), local_enabled=True,
    ).update(local_enabled=False)


@transaction.atomic
def cancel_job(user, job_id) -> Job:
    job = Job.objects.select_for_update().filter(pk=job_id, user=user).first()
    if job is None:
        raise ApiError("找不到這件工作", code="NOT_FOUND", status_code=404)
    if job.status in (Job.Status.COMPLETED, Job.Status.FAILED, Job.Status.CANCELLED):
        raise ApiError("這件工作已結束", code="JOB_NOT_ACTIVE", status_code=409)

    active = Attempt.objects.select_for_update().filter(job=job, ended_at__isnull=True).first()
    if active is not None:
        end_attempt(active, "cancelled", "使用者取消")
    job.status = Job.Status.CANCELLED
    job.stage = "已取消"
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "stage", "completed_at"])
    record("job", f"{job.filename} 已取消", user=user, job=job)
    return job


@transaction.atomic
def retry_job(user, job_id) -> Job:
    job = Job.objects.select_for_update().filter(pk=job_id, user=user).first()
    if job is None:
        raise ApiError("找不到這件工作", code="NOT_FOUND", status_code=404)
    if job.status not in (Job.Status.FAILED, Job.Status.CANCELLED):
        raise ApiError("只有失敗或已取消的工作可以重送", code="JOB_NOT_RETRYABLE", status_code=409)

    job.status = Job.Status.QUEUED
    job.attempt_count = 0
    job.error = ""
    job.stage = "等待可用設備"
    job.progress = None
    job.completed_at = None
    job.save(update_fields=["status", "attempt_count", "error", "stage", "progress", "completed_at"])
    record("job", f"{job.filename} 重新送出", user=user, job=job)
    return job


def check_daily_quota(user, file_count: int) -> None:
    since = timezone.now() - timedelta(days=1)
    used = Job.objects.filter(user=user, created_at__gte=since).count()
    if used + file_count > user.daily_limit:
        raise ApiError(
            f"超過每日上限({user.daily_limit} 個檔案)", code="QUOTA_EXCEEDED", status_code=429,
        )
