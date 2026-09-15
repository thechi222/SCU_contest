from datetime import datetime
from typing import Literal
from pydantic import BaseModel

Role          = Literal["student", "staff", "external"]
MachineStatus = Literal["idle", "rented", "offline"]
BookingStatus = Literal["pending", "active", "done", "cancelled"]


class User(BaseModel):
    id: str
    email: str
    name: str
    role: Role                 # 依 email 網域自動判定
    credit: float              # 虛擬額度


class Machine(BaseModel):
    id: str
    name: str
    cpu_model: str
    gpu_model: str | None
    ram_gb: int
    gpu_vram_gb: int | None
    status: MachineStatus
    owner_dept: str
    price_per_hour: dict[str, float]   # {"student": 10, "staff": 20, "external": 50}


class BookingCreate(BaseModel):
    machine_id: str
    start_time: datetime
    end_time: datetime


class Booking(BaseModel):
    id: str
    user_id: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    access_url: str | None     # 容器啟動後才有值
    estimated_cost: float


class AgentHeartbeat(BaseModel):
    machine_id: str
    cpu_percent: float
    ram_percent: float
    gpu_percent: float | None
    gpu_vram_used_gb: float | None
    timestamp: datetime


class UsageReport(BaseModel):
    booking_id: str
    duration_hours: float
    cpu_avg: float
    gpu_avg: float | None
    cost: float
    summary_text: str          # AI 生成的摘要


class AIAssistRequest(BaseModel):
    user_id: str
    message: str               # 自然語言需求描述


class AIAssistResponse(BaseModel):
    reply: str                 # 給使用者的自然語言回覆
    booking: Booking | None    # 成功建立預約時帶回
