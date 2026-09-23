from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import usage


class Command(BaseCommand):
    help = "Roll up usage samples into daily totals and prune expired samples (README §4.9)."

    def add_arguments(self, parser):
        parser.add_argument("--day", help="重算指定日期(YYYY-MM-DD),預設為今天")
        parser.add_argument("--days", type=int, default=1, help="從指定日期往前重算幾天")
        parser.add_argument("--prune", action="store_true", help="一併清除逾期的取樣")

    def handle(self, *args, **options):
        if options["day"]:
            try:
                start = date.fromisoformat(options["day"])
            except ValueError:
                raise CommandError("--day 格式應為 YYYY-MM-DD") from None
        else:
            start = timezone.localdate()

        for offset in range(max(1, options["days"])):
            day = start - timedelta(days=offset)
            rows = usage.roll_up(day)
            self.stdout.write(f"{day}: 彙整 {rows} 台設備")

        if options["prune"]:
            self.stdout.write(f"清除逾期取樣 {usage.prune_samples()} 筆")
