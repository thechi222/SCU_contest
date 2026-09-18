from dataclasses import dataclass

from core.models import Batch, User


@dataclass
class AIAssistResult:
    reply: str                 # 給使用者的自然語言回覆
    batch: Batch | None        # 助理代為送出批次時帶回


def handle_ai_request(user: User, message: str) -> AIAssistResult:
    """用 LLM function calling 解析 message,可呼叫下列工具函式:

      describe_queue(user) -> dict
          目前排隊、執行中與已完成的工作數,以及可用設備數。

      submit_batch(user, kind, name, files) -> Batch
          以使用者已上傳的檔案建立批次;kind 只能是 core.profiles.PROFILES 的鍵。

    助理不得自行指定模型、容器或參數;任務類型以外的需求一律以自然語言回覆說明。
    由 AIAssistView 以 AIAssistResponseSerializer 序列化後回傳。
    """
    ...


def generate_usage_summary(batch: Batch) -> str:
    """把一個批次的執行結果轉成摘要,內容須包含檔案數、各次執行的 GPU 秒數與參與設備。
    若加入估算值(例如相較單機的節省時間),須註明計算方式與量測來源。"""
    ...
