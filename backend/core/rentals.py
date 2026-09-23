"""互動式租借的流程(README §4.10)。

與任務派工(§4.5)分開實作,但共用同一批節點與同一條 Agent 通道:
一台節點同時只會有一件工作或一段租借,兩邊在領取時互相檢查。

目前為初步版本:平台端的狀態機、配額與連線資訊轉交已完成,
機台端實際啟動容器與對外通道的方式仍待確認(見 README §4.10 與 docs/architecture.md)。
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core import services
from core.exceptions import ApiError
from core.models import Attempt, Node, Rental
from core.profiles import WORKSPACES


def check_quota(user, minutes: int) -> None:
    if minutes > settings.RENTAL_MAX_MINUTES:
        raise ApiError(
            f"單次租借最長 {settings.RENTAL_MAX_MINUTES} 分鐘",
            code="RENTAL_TOO_LONG", status_code=400,
        )
    if Rental.objects.filter(user=user, status__in=Rental.OPEN).exists():
        raise ApiError("已有一段進行中的租借,請先結束", code="RENTAL_ALREADY_OPEN", status_code=409)

    since = timezone.now() - timedelta(days=1)
    used = (
        Rental.objects.filter(user=user, created_at__gte=since)
        .exclude(status__in=[Rental.Status.CANCELLED, Rental.Status.FAILED])
        .aggregate(total=Sum("minutes"))["total"] or 0
    )
    if used + minutes > settings.RENTAL_DAILY_MINUTES:
        raise ApiError(
            f"超過每日租借上限({settings.RENTAL_DAILY_MINUTES} 分鐘)",
            code="QUOTA_EXCEEDED", status_code=429,
        )


def request_rental(user, workspace: str, minutes: int, purpose: str = "") -> Rental:
    profile = WORKSPACES.get(workspace)
    if profile is None:
        raise ApiError("未知的工作環境", code="VALIDATION_ERROR", status_code=400)
    check_quota(user, minutes)

    rental = Rental.objects.create(
        user=user, workspace=workspace, image=profile["image"],
        minutes=minutes, purpose=purpose[:200],
    )
    services.record("rental", f"申請 {profile['label']} {minutes} 分鐘", user=user)
    return rental


def node_accepts_rental(node: Node) -> bool:
    return bool(node.allow_rental and services.node_accepts_work(node))


@transaction.atomic
def claim_rental(node: Node) -> Rental | None:
    """為節點取出一段租借。節點未開放租借、已有工作或租借時回傳 None。"""
    node = Node.objects.select_for_update().get(pk=node.pk)
    if not node_accepts_rental(node):
        return None
    if Attempt.objects.filter(node=node, ended_at__isnull=True).exists():
        return None
    if Rental.objects.filter(node=node, status__in=Rental.ON_NODE).exists():
        return None

    now = timezone.now()
    candidates = (
        Rental.objects.select_for_update(skip_locked=True)
        .filter(status=Rental.Status.QUEUED)
        .select_related("user")
        .order_by("created_at")
    )
    rental = next(
        (item for item in candidates
         if node.memory_mb >= WORKSPACES.get(item.workspace, {}).get("min_vram_mb", 0)),
        None,
    )
    if rental is None:
        return None

    rental.node = node
    rental.status = Rental.Status.STARTING
    rental.started_at = now          # 節點領取並開始啟動的時間
    rental.lease_until = now + timedelta(seconds=settings.LEASE_SECONDS)
    rental.save(update_fields=["node", "status", "started_at", "lease_until"])
    services.record("rental", f"租借派給 {node.name}", user=rental.user, node=node)
    return rental


@transaction.atomic
def mark_ready(node: Node, rental_id, connect_url: str, connect_token: str, connection: dict) -> Rental:
    """Agent 啟動容器並備妥連線通道後回報。時數自此刻起算。"""
    rental = (
        Rental.objects.select_for_update()
        .filter(pk=rental_id, node=node, status=Rental.Status.STARTING)
        .first()
    )
    if rental is None:
        raise ApiError("這段租借已結束", code="RENTAL_NOT_ACTIVE", status_code=409)

    now = timezone.now()
    rental.status = Rental.Status.ACTIVE
    rental.connect_url = connect_url[:300]
    rental.connect_token = connect_token[:120]
    rental.connection = connection
    rental.expires_at = now + timedelta(minutes=rental.minutes)
    rental.lease_until = now + timedelta(seconds=settings.LEASE_SECONDS)
    rental.save(update_fields=[
        "status", "connect_url", "connect_token", "connection", "expires_at", "lease_until",
    ])
    services.record("rental", "容器已啟動,可以連線", user=rental.user, node=node)
    return rental


@transaction.atomic
def renew_lease(node: Node, rental_id) -> bool:
    """續約成功回傳 True;租借已結束、時數用盡或機主收回時回傳 False,Agent 應立即停止容器。"""
    rental = (
        Rental.objects.select_for_update()
        .filter(pk=rental_id, node=node, status__in=Rental.ON_NODE)
        .select_related("user")
        .first()
    )
    if rental is None:
        return False
    now = timezone.now()
    if not node_accepts_rental(node):
        finish(rental, Rental.Status.ENDED, "機主收回設備", now=now)
        return False
    if rental.expires_at and rental.expires_at <= now:
        finish(rental, Rental.Status.EXPIRED, "租借時間到期", now=now)
        return False

    rental.lease_until = now + timedelta(seconds=settings.LEASE_SECONDS)
    rental.save(update_fields=["lease_until"])
    return True


def finish(rental: Rental, status: str, reason: str, *, now=None) -> Rental:
    """結束一段租借並清除連線資訊(token 不再保留)。"""
    rental.status = status
    rental.end_reason = reason[:200]
    rental.ended_at = now or timezone.now()
    rental.connect_token = ""
    rental.connect_url = ""
    rental.lease_until = None
    rental.save(update_fields=[
        "status", "end_reason", "ended_at", "connect_token", "connect_url", "lease_until",
    ])
    services.record("rental", f"租借結束:{reason}", user=rental.user, node=rental.node)
    return rental


@transaction.atomic
def cancel_rental(user, rental_id) -> Rental:
    rental = Rental.objects.select_for_update().filter(pk=rental_id, user=user).first()
    if rental is None:
        raise ApiError("找不到這段租借", code="NOT_FOUND", status_code=404)
    if rental.status not in Rental.OPEN:
        raise ApiError("這段租借已結束", code="RENTAL_NOT_ACTIVE", status_code=409)

    if rental.status == Rental.Status.QUEUED:
        return finish(rental, Rental.Status.CANCELLED, "使用者取消")
    # 已在節點上:先標記結束中,Agent 於下一次心跳收到 stop 後停止容器並回報
    rental.status = Rental.Status.ENDING
    rental.end_reason = "使用者結束"
    rental.connect_token = ""
    rental.save(update_fields=["status", "end_reason", "connect_token"])
    services.record("rental", "使用者結束租借,等待容器停止", user=user, node=rental.node)
    return rental


@transaction.atomic
def agent_ended(node: Node, rental_id, reason: str) -> Rental:
    rental = (
        Rental.objects.select_for_update()
        .filter(pk=rental_id, node=node, status__in=Rental.ON_NODE)
        .select_related("user")
        .first()
    )
    if rental is None:
        raise ApiError("這段租借已結束", code="RENTAL_NOT_ACTIVE", status_code=409)
    status = Rental.Status.FAILED if rental.status == Rental.Status.STARTING else Rental.Status.ENDED
    return finish(rental, status, reason or "容器已停止")


def expire_rentals() -> int:
    """由排程器呼叫:處理逾時的租借。

      * 啟動中逾時或失去心跳:退回佇列,由其他設備接手
      * 使用中失去心跳:標記失敗(容器內的狀態無法轉移)
      * 時數到期:結束
    """
    now = timezone.now()
    handled = 0
    start_deadline = now - timedelta(seconds=settings.RENTAL_START_SECONDS)

    for rental in Rental.objects.filter(status__in=Rental.ON_NODE).select_related("user", "node"):
        with transaction.atomic():
            fresh = (
                Rental.objects.select_for_update()
                .filter(pk=rental.pk, status__in=Rental.ON_NODE).select_related("user", "node").first()
            )
            if fresh is None:
                continue
            lost = fresh.lease_until is not None and fresh.lease_until < now
            if fresh.status == Rental.Status.STARTING and (lost or fresh.started_at < start_deadline):
                fresh.status = Rental.Status.QUEUED
                fresh.node = None
                fresh.started_at = None
                fresh.lease_until = None
                fresh.save(update_fields=["status", "node", "started_at", "lease_until"])
                services.record("rental", "設備未能啟動容器,重新排隊", user=fresh.user)
                handled += 1
            elif lost:
                finish(fresh, Rental.Status.FAILED, "設備失去聯繫", now=now)
                handled += 1
            elif fresh.expires_at is not None and fresh.expires_at <= now:
                finish(fresh, Rental.Status.EXPIRED, "租借時間到期", now=now)
                handled += 1
    return handled
