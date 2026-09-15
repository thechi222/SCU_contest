from datetime import datetime
from typing import Literal
from pydantic import BaseModel

class Machine(BaseModel):
    id: str
    name: str
    cpu_model: str
    gpu_model: str | None
    ram_gb: int
    gpu_vram_gb: int | None
    status: Literal["idle", "rented", "offline"]
    owner_dept: str

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
    status: Literal["pending", "active", "done", "cancelled"]
    access_url: str | None

class AgentHeartbeat(BaseModel):
    machine_id: str
    cpu_percent: float
    ram_percent: float
    gpu_percent: float | None
    gpu_vram_used_gb: float | None
    timestamp: datetime

class AIAssistRequest(BaseModel):
    user_id: str
    message: str

class AIAssistResponse(BaseModel):
    reply: str
    booking: Booking | None
