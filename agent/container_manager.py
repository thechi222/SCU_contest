def start_session_container(
    machine_id: str,
    booking_id: str,
    cpu_limit: float,        # 例如 2.0 = 2 核,取自環境變數 AGENT_CPU_LIMIT
    mem_limit_gb: int,       # 取自環境變數 AGENT_MEM_LIMIT_GB
    gpu: bool,               # True 時以 --gpus 指派整張 GPU,由該預約獨占
) -> str:
    """啟動限流 Docker 容器,回傳可存取的 URL(code-server / Jupyter token URL)。
    Docker 無法限制 GPU 使用率與顯示記憶體,因此 GPU 一律整張指派。"""
    ...


def stop_session_container(booking_id: str) -> None:
    """銷毀容器、清除暫存資料、回收資源。由 stop 任務觸發;
    超過任務的 end_time 仍未收到 stop 任務時,Agent 應自行呼叫本函式。"""
    ...
