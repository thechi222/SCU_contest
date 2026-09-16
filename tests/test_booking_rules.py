"""預約規則的契約測試(README §4.2、§4.5)。"""

from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import AvailabilityWindow, Booking, Machine, User
from core.serializers import BookingCreateSerializer

pending_implementation = pytest.mark.xfail(
    raises=NotImplementedError, strict=True, reason="待 §6.1 實作;完成後移除此標記",
)


def booking_payload(start, end, machine_id="lab-gpu-01"):
    return {"machine_id": machine_id, "start_time": start.isoformat(), "end_time": end.isoformat()}


def make_user(email):
    return User.objects.create_user(
        username=email, email=email, name=email, role="student", password="unused-password",
    )


@pytest.fixture
def machine(db):
    machine = Machine.objects.create(
        id="lab-gpu-01", name="lab", cpu_model="cpu", ram_gb=16, owner_dept="dept", status="idle",
    )
    now = timezone.now()
    AvailabilityWindow.objects.create(machine=machine, start_time=now, end_time=now + timedelta(days=3))
    return machine


def test_booking_end_must_be_after_start():
    start = timezone.now() + timedelta(hours=1)
    serializer = BookingCreateSerializer(data=booking_payload(start, start))
    assert not serializer.is_valid()
    assert "end_time" in serializer.errors


def test_booking_cannot_start_in_the_past():
    start = timezone.now().replace(year=2000)
    serializer = BookingCreateSerializer(data=booking_payload(start, start + timedelta(hours=2)))
    assert not serializer.is_valid()
    assert "start_time" in serializer.errors


@pending_implementation
def test_overlapping_bookings_only_one_succeeds(client, machine):
    client.force_login(make_user("tester@scu.edu.tw"))
    tomorrow = (timezone.localtime() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    slots = [(10, 12), (11, 13), (10.5, 11.5), (9, 10.5), (11.9, 12.5)]

    responses = [
        client.post(
            "/api/bookings",
            booking_payload(tomorrow + timedelta(hours=start), tomorrow + timedelta(hours=end)),
            content_type="application/json",
        )
        for start, end in slots
    ]

    assert [r.status_code for r in responses].count(201) == 1
    assert all(r.json()["code"] == "BOOKING_CONFLICT" for r in responses if r.status_code != 201)


@pending_implementation
def test_booking_outside_availability_is_rejected(client, machine):
    client.force_login(make_user("tester@scu.edu.tw"))
    start = timezone.now() + timedelta(days=5)
    response = client.post(
        "/api/bookings", booking_payload(start, start + timedelta(hours=1)), content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "OUTSIDE_AVAILABILITY"


@pending_implementation
def test_cannot_view_other_users_booking(client, machine):
    start = timezone.now() + timedelta(hours=1)
    booking = Booking.objects.create(
        user=make_user("owner@scu.edu.tw"), machine=machine,
        start_time=start, end_time=start + timedelta(hours=1),
    )
    client.force_login(make_user("other@scu.edu.tw"))
    response = client.get(f"/api/bookings/{booking.id}")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
