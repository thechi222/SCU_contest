from dataclasses import dataclass

from core.models import Booking, UsageReport, User


@dataclass
class AIAssistResult:
    reply: str                   # 給使用者的自然語言回覆
    booking: Booking | None      # 成功建立預約時帶回


def handle_ai_request(user: User, message: str) -> AIAssistResult:
    """用 LLM function calling 解析 message,工具函式使用 core.services 的:

      list_available_machines(need_gpu, min_vram_gb, start, end) -> list[Machine]
      create_booking(user, machine_id, start, end) -> Booking

    create_booking 拋出 ApiError 時,將錯誤原因轉為自然語言回覆,booking 為 None。
    由 AIAssistView 以 AIAssistResponseSerializer 序列化後回傳。
    """
    ...


def generate_usage_summary(report: UsageReport) -> str:
    """把使用紀錄轉成摘要,內容須包含使用時長與平均使用率。
    若加入估算值(例如相較雲端 GPU 的等值費用、碳排),須註明計算假設與資料來源。"""
    ...
