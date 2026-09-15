from fastapi import APIRouter

from app.models import Booking, BookingCreate, UsageReport

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=Booking)
def create_booking(payload: BookingCreate) -> Booking:
    raise NotImplementedError


@router.get("/{booking_id}", response_model=Booking)
def get_booking(booking_id: str) -> Booking:
    raise NotImplementedError


@router.post("/{booking_id}/cancel", response_model=Booking)
def cancel_booking(booking_id: str) -> Booking:
    raise NotImplementedError


@router.get("/{booking_id}/report", response_model=UsageReport)
def get_booking_report(booking_id: str) -> UsageReport:
    raise NotImplementedError
