from apscheduler.schedulers.blocking import BlockingScheduler
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from core.scheduling import sync_booking_tasks

SYNC_INTERVAL_SECONDS = 30


def run_sync() -> None:
    # 長時間執行的行程須自行釋放逾時的資料庫連線
    close_old_connections()
    try:
        sync_booking_tasks()
    finally:
        close_old_connections()


class Command(BaseCommand):
    help = "Run the booking scheduler (README §6.1). Scans the database immediately and then every 30 seconds."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_job(
            run_sync, "interval", seconds=SYNC_INTERVAL_SECONDS,
            next_run_time=timezone.now(), max_instances=1, coalesce=True,
        )
        self.stdout.write("Scheduler started.")
        scheduler.start()
