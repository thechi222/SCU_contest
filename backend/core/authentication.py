import hashlib
import secrets

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import Node


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_pairing_code() -> str:
    return secrets.token_urlsafe(9)


class NodeTokenAuthentication(BaseAuthentication):
    """以 Authorization: Bearer <node token> 辨識節點;驗證成功時 request.auth 為該 Node。"""

    def authenticate(self, request):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme != "Bearer" or not token:
            return None
        node = Node.objects.filter(token_hash=hash_token(token)).first()
        if node is None or node.revoked:
            raise AuthenticationFailed("節點 token 無效或已撤銷")
        return AnonymousUser(), node
