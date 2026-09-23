"""閒置算力儀表板的取樣、彙整與匯出(README §4.9)。

資料分兩層:
  * `UsageSample` — 心跳時的即時取樣,保留 `settings.USAGE_RETENTION_DAYS` 天,供繪圖與匯出。
  * `NodeDailyUsage` — 每日彙整,長期保存;取樣被清除後統計數字仍在。

本模組不改動派工協定(§4.5),只讀取節點與工作狀態。
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from core.models import Attempt, Job, Node, NodeDailyUsage, Rental, UsageSample

MAX_INTERVAL_SECONDS = 15 * 60   # 節點離線再回來時,不把整段空窗計入區間


def is_online(node: Node, *, now=None) -> bool:
    if node.last_seen is None:
        return False
    now = now or timezone.now()
    return (now - node.last_seen).total_seconds() <= settings.NODE_OFFLINE_SECONDS


def current_state(node: Node, *, now=None, has_attempt=None, has_rental=None) -> str:
    """節點目前的狀態。呼叫端已知是否有工作或租借時可直接傳入,避免重複查詢。"""
    state = UsageSample.State
    if node.revoked:
        return state.PAUSED
    if not is_online(node, now=now):
        return state.OFFLINE
    if has_rental is None:
        has_rental = Rental.objects.filter(node=node, status__in=Rental.ON_NODE).exists()
    if has_rental:
        return state.RENTED
    if has_attempt is None:
        has_attempt = Attempt.objects.filter(node=node, ended_at__isnull=True).exists()
    if has_attempt:
        return state.BUSY
    if not (node.sharing and node.local_enabled):
        return state.PAUSED
    return state.IDLE


def record_sample(node: Node, *, now=None, has_attempt=None, has_rental=None) -> UsageSample | None:
    """心跳時呼叫。每台節點最多每 USAGE_SAMPLE_SECONDS 留一筆,未達間隔時回傳 None。"""
    now = now or timezone.now()
    last = node.usage_samples.order_by("-captured_at").first()
    if last is not None:
        elapsed = (now - last.captured_at).total_seconds()
        if elapsed < settings.USAGE_SAMPLE_SECONDS:
            return None
        interval = min(elapsed, MAX_INTERVAL_SECONDS)
    else:
        interval = float(settings.USAGE_SAMPLE_SECONDS)

    state = current_state(node, now=now, has_attempt=has_attempt, has_rental=has_rental)
    telemetry = node.telemetry or {}
    working = state in (UsageSample.State.BUSY, UsageSample.State.RENTED)
    return UsageSample.objects.create(
        node=node,
        captured_at=now,
        state=state,
        gpu_utilization=_number(telemetry.get("gpu_utilization")),
        memory_used_mb=_positive_int(telemetry.get("memory_used_mb")),
        temperature_c=_number(telemetry.get("temperature_c")),
        power_w=_number(telemetry.get("power_w")),
        interval_seconds=interval,
        busy_seconds=interval if working else 0.0,
    )


def series(nodes, *, hours=None, now=None) -> dict:
    """每台節點最近數小時的取樣,回傳 {node_id: [{t, u, state}, …]}。"""
    hours = hours or settings.USAGE_SERIES_HOURS
    since = (now or timezone.now()) - timedelta(hours=hours)
    points: dict = {node.id: [] for node in nodes}
    samples = (
        UsageSample.objects.filter(node__in=nodes, captured_at__gte=since)
        .order_by("captured_at")
        .values("node_id", "captured_at", "gpu_utilization", "state")
    )
    for sample in samples:
        points[sample["node_id"]].append({
            "t": sample["captured_at"],
            "u": sample["gpu_utilization"],
            "state": sample["state"],
        })
    return points


def overview(user, *, hours=None, now=None) -> dict:
    """儀表板單一端點:平台總覽、各機台目前狀況與最近曲線、每日用量。"""
    now = now or timezone.now()
    nodes = list(Node.objects.filter(revoked=False).select_related("owner").order_by("name"))
    busy_nodes = set(
        Attempt.objects.filter(ended_at__isnull=True, node__in=nodes).values_list("node_id", flat=True)
    )
    rented_nodes = set(
        Rental.objects.filter(status__in=Rental.ON_NODE, node__in=nodes).values_list("node_id", flat=True)
    )
    points = series(nodes, hours=hours, now=now)
    today = timezone.localdate(now)
    today_rows = {
        row.node_id: row for row in NodeDailyUsage.objects.filter(node__in=nodes, day=today)
    }

    rows = []
    for node in nodes:
        state = current_state(
            node, now=now,
            has_attempt=node.id in busy_nodes, has_rental=node.id in rented_nodes,
        )
        telemetry = node.telemetry or {}
        row = today_rows.get(node.id)
        rows.append({
            "id": str(node.id),
            "name": node.name,
            "owner_name": node.owner.name,
            "is_mine": node.owner_id == user.id,
            "gpu_name": node.gpu_name,
            "memory_mb": node.memory_mb,
            "kinds": sorted(node.capabilities),
            "allow_rental": node.allow_rental,
            "state": state,
            "gpu_utilization": _number(telemetry.get("gpu_utilization")),
            "memory_used_mb": _positive_int(telemetry.get("memory_used_mb")),
            "temperature_c": _number(telemetry.get("temperature_c")),
            "power_w": _number(telemetry.get("power_w")),
            "last_seen": node.last_seen,
            "today": {
                "busy_seconds": row.busy_seconds if row else 0.0,
                "rented_seconds": row.rented_seconds if row else 0.0,
                "idle_seconds": row.idle_seconds if row else 0.0,
                "gpu_seconds": row.gpu_seconds if row else 0.0,
                "jobs_completed": row.jobs_completed if row else 0,
            },
            "series": points.get(node.id, []),
        })

    online = [row for row in rows if row["state"] != UsageSample.State.OFFLINE]
    idle = [row for row in online if row["state"] == UsageSample.State.IDLE]
    working = [row for row in online if row["state"] in (UsageSample.State.BUSY, UsageSample.State.RENTED)]
    utilizations = [row["gpu_utilization"] for row in online if row["gpu_utilization"] is not None]

    return {
        "generated_at": now,
        "totals": {
            "nodes_total": len(rows),
            "nodes_online": len(online),
            "nodes_idle": len(idle),
            "nodes_working": len(working),
            "idle_vram_mb": sum(row["memory_mb"] for row in idle),
            "online_vram_mb": sum(row["memory_mb"] for row in online),
            "avg_utilization": round(sum(utilizations) / len(utilizations), 1) if utilizations else None,
            "jobs_queued": Job.objects.filter(status__in=Job.PENDING).count(),
            "jobs_running": Job.objects.filter(status__in=Job.ACTIVE).count(),
            "rentals_open": Rental.objects.filter(status__in=Rental.OPEN).count(),
        },
        "nodes": rows,
        "days": daily_totals(),
        "settings": {
            "sample_seconds": settings.USAGE_SAMPLE_SECONDS,
            "retention_days": settings.USAGE_RETENTION_DAYS,
            "series_hours": hours or settings.USAGE_SERIES_HOURS,
        },
    }


def daily_totals(days: int = 14) -> list[dict]:
    """全平台每日用量,新到舊。"""
    since = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        NodeDailyUsage.objects.filter(day__gte=since)
        .values("day")
        .annotate(
            busy_seconds=Sum("busy_seconds"), rented_seconds=Sum("rented_seconds"),
            idle_seconds=Sum("idle_seconds"), gpu_seconds=Sum("gpu_seconds"),
            jobs_completed=Sum("jobs_completed"),
        )
        .order_by("-day")
    )
    return list(rows)


def roll_up(day=None) -> int:
    """由取樣重算某日的彙整。可重複執行,結果只取決於當日取樣與 attempt 紀錄。"""
    day = day or timezone.localdate()
    start = timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())
    end = start + timedelta(days=1)

    totals: dict = {}
    samples = UsageSample.objects.filter(captured_at__gte=start, captured_at__lt=end).values(
        "node_id", "state", "interval_seconds", "gpu_utilization",
    )
    for sample in samples:
        bucket = totals.setdefault(sample["node_id"], {
            "busy_seconds": 0.0, "rented_seconds": 0.0, "idle_seconds": 0.0,
            "offline_seconds": 0.0, "samples": 0, "utilization_sum": 0.0,
            "utilization_count": 0, "peak_utilization": None,
        })
        seconds = sample["interval_seconds"] or 0.0
        field = {
            UsageSample.State.BUSY: "busy_seconds",
            UsageSample.State.RENTED: "rented_seconds",
            UsageSample.State.IDLE: "idle_seconds",
        }.get(sample["state"], "offline_seconds")
        bucket[field] += seconds
        bucket["samples"] += 1
        utilization = sample["gpu_utilization"]
        if utilization is not None:
            bucket["utilization_sum"] += utilization
            bucket["utilization_count"] += 1
            peak = bucket["peak_utilization"]
            bucket["peak_utilization"] = utilization if peak is None else max(peak, utilization)

    finished = (
        Attempt.objects.filter(ended_at__gte=start, ended_at__lt=end, outcome="succeeded")
        .values("node_id", "metrics")
    )
    for attempt in finished:
        bucket = totals.setdefault(attempt["node_id"], {
            "busy_seconds": 0.0, "rented_seconds": 0.0, "idle_seconds": 0.0,
            "offline_seconds": 0.0, "samples": 0, "utilization_sum": 0.0,
            "utilization_count": 0, "peak_utilization": None,
        })
        bucket["jobs_completed"] = bucket.get("jobs_completed", 0) + 1
        gpu_seconds = (attempt["metrics"] or {}).get("gpu_seconds")
        if isinstance(gpu_seconds, (int, float)) and not isinstance(gpu_seconds, bool):
            bucket["gpu_seconds"] = bucket.get("gpu_seconds", 0.0) + float(gpu_seconds)

    for node_id, bucket in totals.items():
        count = bucket["utilization_count"]
        NodeDailyUsage.objects.update_or_create(
            node_id=node_id, day=day,
            defaults={
                "busy_seconds": bucket["busy_seconds"],
                "rented_seconds": bucket["rented_seconds"],
                "idle_seconds": bucket["idle_seconds"],
                "offline_seconds": bucket["offline_seconds"],
                "gpu_seconds": bucket.get("gpu_seconds", 0.0),
                "jobs_completed": bucket.get("jobs_completed", 0),
                "samples": bucket["samples"],
                "avg_utilization": round(bucket["utilization_sum"] / count, 1) if count else None,
                "peak_utilization": bucket["peak_utilization"],
            },
        )
    return len(totals)


def prune_samples(now=None) -> int:
    """清除逾期的取樣。每日彙整不受影響。"""
    deadline = (now or timezone.now()) - timedelta(days=settings.USAGE_RETENTION_DAYS)
    deleted, _ = UsageSample.objects.filter(captured_at__lt=deadline).delete()
    return deleted


def export_rows(*, days: int = 30, node=None):
    """CSV 匯出用的逐列資料(每日彙整)。"""
    since = timezone.localdate() - timedelta(days=days - 1)
    rows = NodeDailyUsage.objects.filter(day__gte=since).select_related("node").order_by("-day", "node__name")
    if node is not None:
        rows = rows.filter(node=node)
    yield [
        "day", "node", "gpu", "busy_seconds", "rented_seconds", "idle_seconds",
        "offline_seconds", "gpu_seconds", "jobs_completed", "avg_utilization", "peak_utilization",
    ]
    for row in rows:
        yield [
            row.day.isoformat(), row.node.name, row.node.gpu_name,
            round(row.busy_seconds), round(row.rented_seconds), round(row.idle_seconds),
            round(row.offline_seconds), round(row.gpu_seconds), row.jobs_completed,
            row.avg_utilization if row.avg_utilization is not None else "",
            row.peak_utilization if row.peak_utilization is not None else "",
        ]


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _positive_int(value):
    number = _number(value)
    return int(number) if number is not None and number >= 0 else None
