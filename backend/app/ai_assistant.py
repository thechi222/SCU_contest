from app.models import AIAssistResponse


def handle_ai_request(user_id: str, message: str) -> AIAssistResponse:
    """
    用 LLM function calling 解析 message,可呼叫下列工具函式:
      - list_available_machines(need_gpu: bool, min_vram_gb: int | None,
                                  start: datetime, end: datetime) -> list[Machine]
      - create_booking(user_id: str, machine_id: str,
                        start: datetime, end: datetime) -> Booking
    回傳自然語言回覆,以及(若成功建立)對應的 Booking。
    """
    raise NotImplementedError
