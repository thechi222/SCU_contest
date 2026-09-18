from core import services


def sweep() -> dict:
    """由 run_scheduler 每秒呼叫一次,可重複執行:

      - 租約逾時的 attempt:結束該次執行,工作重新排隊或標記失敗
      - 心跳中斷的節點:視為未開放接單
    """
    return {
        "expired_attempts": services.expire_leases(),
        "offline_nodes": services.mark_offline_nodes(),
    }
