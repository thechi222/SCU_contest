from django.conf import settings
from django.utils import timezone

from core import rentals, services, usage

_last_rollup = None   # 排程器為單一行程,用量彙整不需每秒重算


def sweep() -> dict:
    """由 run_scheduler 每秒呼叫一次,可重複執行:

      - 租約逾時的 attempt:結束該次執行,工作重新排隊或標記失敗
      - 心跳中斷的節點:視為未開放接單
      - 逾時或到期的互動式租借:退回佇列、標記失敗或結束
      - 每 USAGE_ROLLUP_SECONDS 一次:重算當日用量彙整並清除逾期取樣
    """
    global _last_rollup
    result = {
        "expired_attempts": services.expire_leases(),
        "offline_nodes": services.mark_offline_nodes(),
        "expired_rentals": rentals.expire_rentals(),
    }

    now = timezone.now()
    if _last_rollup is None or (now - _last_rollup).total_seconds() >= settings.USAGE_ROLLUP_SECONDS:
        _last_rollup = now
        result["usage_rows"] = usage.roll_up()
        result["pruned_samples"] = usage.prune_samples(now=now)
    return result
