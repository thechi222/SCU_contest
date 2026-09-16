import secrets

from django.core.management.base import BaseCommand, CommandError

from core.authentication import hash_agent_token
from core.models import Machine


class Command(BaseCommand):
    help = "Issue a new agent token for a machine, replacing any previous token. The token is shown only once."

    def add_arguments(self, parser):
        parser.add_argument("machine_id")

    def handle(self, *args, machine_id, **options):
        try:
            machine = Machine.objects.get(pk=machine_id)
        except Machine.DoesNotExist as exc:
            raise CommandError(f"machine {machine_id} not found") from exc

        token = secrets.token_urlsafe(32)
        machine.agent_token_hash = hash_agent_token(token)
        machine.save(update_fields=["agent_token_hash"])
        self.stdout.write(f"AGENT_TOKEN for {machine_id}: {token}")
