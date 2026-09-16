from dataclasses import dataclass

from core.models import Booking, UsageReport, User


@dataclass
class AIAssistResult:
    reply: str                   # 給使用者的自然語言回覆
    booking: Booking | None      # 成功建立預約時帶回


def handle_ai_request(user: User, message: str) -> AIAssistResult:
    """用 LLM function calling 解析 message,可呼叫下列工具函式:

      list_available_machines(need_gpu: bool,
                              min_vram_gb: int | None,
                              start: datetime,
                              end: datetime) -> list[Machine]

      create_booking(user: User, machine_id: str,
                     start: datetime, end: datetime) -> Booking

    回傳自然語言回覆 + (若成功建立)對應的 Booking。
    由 AIAssistView 以 AIAssistResponseSerializer 序列化後回傳。
    """
    ...


def generate_usage_summary(report: UsageReport) -> str:
    """把使用紀錄轉成摘要,內容需包含:使用時長、平均使用率、
    花費、相較雲端 GPU 省下的金額、估算省下的碳排。"""
    ...
