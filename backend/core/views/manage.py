"""管理台:帳號審核與全平台使用情形(README §4.12)。

只有管理員(`is_staff`)可存取。管理員身分的取得方式見 §4.11:
註冊時填入 `ADMIN_INVITE_CODE`,或由既有管理員以 `grant_admin` 指令、管理台或 Django Admin 指派。
"""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core import usage
from core.exceptions import ApiError
from core.models import Batch, Event, Job, Node, Rental, User
from core.permissions import IsPlatformAdmin
from core.serializers import (
    AdminUserSerializer, AdminUserUpdateSerializer, EventSerializer, RentalSerializer,
)


class AdminAPIView(APIView):
    permission_classes = [IsPlatformAdmin]


class AdminOverviewView(AdminAPIView):
    """管理台單一來源:待審核帳號、所有帳號與使用情形、工作與租借概況。"""

    def get(self, request):
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        users = (
            User.objects.annotate(
                jobs_total=Count("jobs", distinct=True),
                jobs_today=Count("jobs", filter=Q(jobs__created_at__gte=day_ago), distinct=True),
                nodes_total=Count("nodes", filter=Q(nodes__revoked=False), distinct=True),
            )
            .order_by("-date_joined")
        )
        pending = [user for user in users if not user.is_active]

        jobs = Job.objects.select_related("user").order_by("-created_at")[:50]
        rentals = Rental.objects.select_related("user", "node").order_by("-created_at")[:20]
        events = Event.objects.select_related("user").order_by("-id")[:50]

        return Response({
            "summary": {
                "users_total": users.count(),
                "users_pending": len(pending),
                "users_admin": sum(1 for user in users if user.is_staff),
                "nodes_total": Node.objects.filter(revoked=False).count(),
                "jobs_today": Job.objects.filter(created_at__gte=day_ago).count(),
                "jobs_queued": Job.objects.filter(status__in=Job.PENDING).count(),
                "jobs_running": Job.objects.filter(status__in=Job.ACTIVE).count(),
                "batches_today": Batch.objects.filter(created_at__gte=day_ago).count(),
                "rentals_open": Rental.objects.filter(status__in=Rental.OPEN).count(),
            },
            "pending_users": AdminUserSerializer(pending, many=True).data,
            "users": AdminUserSerializer(users, many=True).data,
            "jobs": [
                {
                    "id": str(job.id), "filename": job.filename, "kind": job.kind,
                    "status": job.status, "stage": job.stage, "attempt_count": job.attempt_count,
                    "user": job.user.student_id, "user_name": job.user.name,
                    "created_at": job.created_at, "completed_at": job.completed_at,
                }
                for job in jobs
            ],
            "rentals": RentalSerializer(rentals, many=True).data,
            "events": [
                {**EventSerializer(event).data, "user": event.user.student_id if event.user else None}
                for event in events
            ],
            "usage": usage.overview(request.user)["totals"],
            "days": usage.daily_totals(),
        })


class AdminUserDetailView(AdminAPIView):
    """核可、停用或調整單一帳號的配額與身分。"""

    def patch(self, request, user_id):
        target = User.objects.filter(pk=user_id).first()
        if target is None:
            raise ApiError("找不到這個帳號", code="NOT_FOUND", status_code=404)

        data = AdminUserUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        payload = dict(data.validated_data)

        if target.pk == request.user.pk and payload.get("is_admin") is False:
            raise ApiError("不能移除自己的管理權限", code="VALIDATION_ERROR", status_code=400)
        if target.pk == request.user.pk and payload.get("is_active") is False:
            raise ApiError("不能停用自己的帳號", code="VALIDATION_ERROR", status_code=400)

        if "is_admin" in payload:
            target.is_staff = payload.pop("is_admin")
        for field, value in payload.items():
            setattr(target, field, value)
        target.save()

        from core import services
        services.record("admin", f"{request.user.student_id} 調整帳號 {target.student_id}", user=target)
        return Response(AdminUserSerializer(target).data)
