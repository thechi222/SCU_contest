def start_session_container(
    machine_id: str, booking_id: str,
    cpu_limit: float, mem_limit_gb: int, gpu: bool,
) -> str:
    """啟動限流 Docker 容器,回傳可存取的 URL(如 code-server token URL)"""
    raise NotImplementedError


def stop_session_container(booking_id: str) -> None:
    """銷毀容器、回收資源"""
    raise NotImplementedError
