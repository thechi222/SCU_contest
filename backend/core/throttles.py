import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """依登入 email 計次,避免經同一個 tunnel 連入的受測者共用 IP 額度。"""

    scope = "login"

    def get_cache_key(self, request, view):
        data = request.data
        email = data.get("email", "") if isinstance(data, dict) else ""
        ident = email.strip().lower() if isinstance(email, str) and email.strip() else self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(ident.encode()).hexdigest(),
        }
