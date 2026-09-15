from fastapi import FastAPI

from app.models import (
    Machine,
    BookingCreate,
    Booking,
    AgentHeartbeat,
    AIAssistRequest,
    AIAssistResponse,
)

app = FastAPI(title="PowerShare API")


@app.get("/api/machines", response_model=list[Machine])
def list_machines() -> list[Machine]:
    raise NotImplementedError


@app.post("/api/bookings", response_model=Booking)
def create_booking(booking: BookingCreate) -> Booking:
    raise NotImplementedError


@app.get("/api/bookings/{booking_id}", response_model=Booking)
def get_booking(booking_id: str) -> Booking:
    raise NotImplementedError


@app.post("/api/bookings/{booking_id}/cancel", response_model=Booking)
def cancel_booking(booking_id: str) -> Booking:
    raise NotImplementedError


@app.post("/api/agent/heartbeat")
def agent_heartbeat(heartbeat: AgentHeartbeat) -> None:
    raise NotImplementedError


@app.post("/api/ai/assist", response_model=AIAssistResponse)
def ai_assist(request: AIAssistRequest) -> AIAssistResponse:
    raise NotImplementedError
