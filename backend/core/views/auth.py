from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.exceptions import ApiError
from core.models import User
from core.serializers import (
    LoginSerializer, PasswordChangeSerializer, RegisterSerializer, UserSerializer,
)
from core.throttles import LoginRateThrottle, RegisterRateThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request,
            student_id=data.validated_data["student_id"],
            password=data.validated_data["password"],
        )
        if user is None:
            inactive = User.objects.filter(
                student_id=data.validated_data["student_id"], is_active=False,
            ).exists()
            if inactive:
                raise ApiError(
                    "這個帳號尚未啟用,請等待管理者核可", code="ACCOUNT_INACTIVE", status_code=403,
                )
            raise ApiError("學號或密碼不正確", code="LOGIN_FAILED", status_code=403)
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


class RegisterView(APIView):
    """以學號自行註冊。需要審核時帳號先建立為停用狀態,由管理者於 Admin 啟用(README §4.11)。"""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        if not settings.REGISTRATION_OPEN:
            raise ApiError("目前未開放自行註冊", code="REGISTRATION_CLOSED", status_code=403)

        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data

        try:
            validate_password(payload["password"])
        except ValidationError as exc:
            raise ApiError(" ".join(exc.messages), code="VALIDATION_ERROR", status_code=400) from exc

        # 填入正確的管理邀請碼即建立為管理員,並跳過審核(README §4.11)
        invite = (payload.get("invite_code") or "").strip()
        as_admin = bool(settings.ADMIN_INVITE_CODE) and invite == settings.ADMIN_INVITE_CODE
        if invite and not as_admin:
            raise ApiError("管理邀請碼不正確", code="INVITE_CODE_INVALID", status_code=403)

        user = User.objects.create_user(
            student_id=payload["student_id"], password=payload["password"],
            name=payload["name"], role=payload["role"], email=payload.get("email", ""),
            is_active=as_admin or not settings.REGISTRATION_REQUIRE_APPROVAL,
            is_staff=as_admin, is_superuser=as_admin,
        )
        services.record(
            "auth", f"{user.student_id} 註冊{'管理員' if as_admin else ''}帳號", user=user,
        )

        if not user.is_active:
            return Response(
                {"status": "pending", "detail": "帳號已建立,待管理者核可後才能登入"}, status=201,
            )
        login(request, user)
        return Response(UserSerializer(user).data, status=201)
