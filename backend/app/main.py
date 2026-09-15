from fastapi import FastAPI

from app.models import AIAssistRequest, AIAssistResponse
from app.routers import agent, bookings, machines

app = FastAPI(title="PowerShare API")

app.include_router(machines.router)
app.include_router(bookings.router)
app.include_router(agent.router)


@app.post("/api/ai/assist", response_model=AIAssistResponse, tags=["ai"])
def ai_assist(payload: AIAssistRequest) -> AIAssistResponse:
    raise NotImplementedError
