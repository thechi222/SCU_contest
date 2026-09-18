from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from core.scheduling import sweep

SWEEP_INTERVAL_SECONDS = 1


def run_sweep() -> None:
    # 長時間執行的行程須自行釋放逾時的資料庫連線
    close_old_connections()
    try:
        sweep()
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = "Expire stale leases and mark offline nodes (README §6.1). Runs every second."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_job(
            run_sweep, "interval", seconds=SWEEP_INTERVAL_SECONDS,
            next_run_time=timezone.now(), max_instances=1, coalesce=True,
        )
        self.stdout.write("Scheduler started.")
        scheduler.start()
