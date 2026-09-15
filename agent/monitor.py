def collect_metrics() -> dict:
    """回傳目前機台 CPU/RAM/GPU 使用率,欄位需符合 AgentHeartbeat"""
    raise NotImplementedError


def send_heartbeat(base_url: str, machine_id: str) -> None:
    """每 10 秒呼叫一次,POST 到 /api/agent/heartbeat"""
    raise NotImplementedError
