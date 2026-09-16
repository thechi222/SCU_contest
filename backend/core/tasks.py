from core.models import AgentTask, Booking


def enqueue_task(booking: Booking, action: str) -> AgentTask:
    """建立預約的 start / stop 任務;同一預約同一動作已有任務時,直接回傳既有任務。"""
    task, _ = AgentTask.objects.get_or_create(
        booking=booking, action=action, defaults={"machine": booking.machine},
    )
    return task
