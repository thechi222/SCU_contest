from fastapi import APIRouter

from app.models import AgentHeartbeat

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/heartbeat")
def receive_heartbeat(heartbeat: AgentHeartbeat) -> None:
    raise NotImplementedError
