from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.exceptions import ApiError
from core.serializers import LoginSerializer, PasswordChangeSerializer, UserSerializer
from core.throttles import LoginRateThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request, email=data.validated_data["email"], password=data.validated_data["password"],
        )
        if user is None:
            raise ApiError("帳號或密碼不正確", code="LOGIN_FAILED", status_code=403)
        login(request, user)
        services.record("auth", "登入", user=user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    def post(self, request):
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if not request.user.check_password(data.validated_data["current_password"]):
            raise ApiError("目前密碼不正確", code="LOGIN_FAILED", status_code=403)
        try:
            validate_password(data.validated_data["new_password"], request.user)
        except ValidationError as exc:
            raise ApiError(" ".join(exc.messages), code="VALIDATION_ERROR", status_code=400) from exc

        request.user.set_password(data.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)
        services.record("auth", "變更密碼", user=request.user)
        return Response(status=204)
