from datetime import datetime

from core.models import Booking, Machine, User


def list_available_machines(
    need_gpu: bool, min_vram_gb: int | None, start: datetime, end: datetime,
) -> list[Machine]:
    """回傳 [start, end) 期間可預約的機台:狀態不是 offline / busy、
    該時段完整落在某個 AvailabilityWindow 內,且不與 pending / active 預約重疊。"""
    ...


def create_booking(user: User, machine_id: str, start: datetime, end: datetime) -> Booking:
    """在 transaction.atomic() 內以 select_for_update() 鎖定該 Machine 列,再依序檢查:

      1. 機台存在                                 否則 ApiError NOT_FOUND (404)
      2. 機台狀態不是 offline / busy               否則 ApiError MACHINE_UNAVAILABLE (409)
      3. 時段完整落在某個 AvailabilityWindow 內     否則 ApiError OUTSIDE_AVAILABILITY (409)
      4. 不與同機台 pending / active 預約重疊       否則 ApiError BOOKING_CONFLICT (409)
         重疊條件:既有.start_time < end 且 既有.end_time > start

    BookingListCreateView 與 AI 助理的 create_booking 工具共用本函式。
    """
    ...
