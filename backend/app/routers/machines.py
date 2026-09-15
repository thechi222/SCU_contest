from fastapi import APIRouter

from app.models import Machine

router = APIRouter(prefix="/api/machines", tags=["machines"])


@router.get("", response_model=list[Machine])
def list_machines() -> list[Machine]:
    raise NotImplementedError
