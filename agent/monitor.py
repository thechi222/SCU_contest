def collect_metrics() -> dict:
    """讀取本機 CPU/RAM/GPU 使用率。回傳欄位需符合 AgentHeartbeat。
    無 GPU 的機器,gpu_* 欄位回 None。"""
    ...


def send_heartbeat(base_url: str, machine_id: str) -> None:
    """每 10 秒呼叫一次,POST collect_metrics() 的結果到 /api/agent/heartbeat。
    Header 須帶 X-Agent-Token,值取自環境變數 AGENT_TOKEN。"""
    ...
