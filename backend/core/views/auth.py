from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from core.throttles import LoginRateThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        """POST /api/auth/login(LoginSerializer)→ UserSerializer"""
        raise NotImplementedError


class LogoutView(APIView):
    def post(self, request):
        """POST /api/auth/logout → 204"""
        raise NotImplementedError


class MeView(APIView):
    def get(self, request):
        """GET /api/auth/me → UserSerializer"""
        raise NotImplementedError
