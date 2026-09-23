import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """依登入學號計次,避免經同一個 tunnel 連入的受測者共用 IP 額度。"""

    scope = "login"

    def get_cache_key(self, request, view):
        data = request.data
        raw = data.get("student_id", "") if isinstance(data, dict) else ""
        ident = raw.strip().upper() if isinstance(raw, str) and raw.strip() else self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(ident.encode()).hexdigest(),
        }


class RegisterRateThrottle(SimpleRateThrottle):
    """註冊依來源位址計次,降低自動化大量建立帳號的風險。"""

    scope = "register"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(self.get_ident(request).encode()).hexdigest(),
        }
