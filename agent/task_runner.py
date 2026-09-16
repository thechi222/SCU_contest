def claim_task(base_url: str) -> dict | None:
    """POST /api/agent/tasks/claim,回傳 AgentTaskSerializer 格式的任務;無任務(204)時回傳 None。
    Header 須帶 X-Agent-Token。"""
    ...


def report_task_result(
    base_url: str,
    task_id: str,
    status: str,                     # "succeeded" 或 "failed"
    access_url: str | None = None,   # start 成功時必填
    error_message: str = "",
) -> None:
    """POST /api/agent/tasks/{task_id}/result。Header 須帶 X-Agent-Token。"""
    ...


def run_forever(base_url: str, machine_id: str) -> None:
    """每 5 秒領取一次任務:start 呼叫 start_session_container(),stop 呼叫
    stop_session_container(),完成後以 report_task_result() 回報。
    機台只發出 outbound 請求,無須開放任何 inbound port。"""
    ...
