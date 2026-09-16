import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasAgentToken(BasePermission):
    def has_permission(self, request, view):
        token = request.headers.get("X-Agent-Token", "")
        expected = settings.AGENT_TOKEN
        return bool(expected) and secrets.compare_digest(token.encode(), expected.encode())
