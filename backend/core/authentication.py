import hashlib

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import Machine


def hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AgentTokenAuthentication(BaseAuthentication):
    """以 X-Agent-Token 辨識機台;驗證成功時 request.auth 為該 Machine。"""

    def authenticate(self, request):
        token = request.headers.get("X-Agent-Token")
        if not token:
            return None
        machine = Machine.objects.filter(agent_token_hash=hash_agent_token(token)).first()
        if machine is None:
            raise AuthenticationFailed("Agent token 無效")
        return AnonymousUser(), machine
