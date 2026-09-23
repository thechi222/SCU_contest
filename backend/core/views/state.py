from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Batch, Event, Node, Rental
from core.profiles import AVAILABLE_KINDS, task_catalog, workspace_catalog
from core.serializers import (
    BatchSerializer, EventSerializer, NodeSerializer, RentalSerializer, UserSerializer,
)


class TaskCatalogView(APIView):
    """公開的任務目錄與互動式租借環境,供服務說明頁與工作台使用。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"tasks": task_catalog(), "workspaces": workspace_catalog()})


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "time": timezone.now()})


class StateView(APIView):
    """前端每 2 秒輪詢一次的彙整端點:目前使用者、設備、批次與事件。"""

    def get(self, request):
        batches = (
            Batch.objects.filter(user=request.user, archived=False)
            .prefetch_related("jobs__artifacts").order_by("-created_at")[:20]
        )
        nodes = Node.objects.filter(revoked=False).select_related("owner").order_by("name")
        events = Event.objects.filter(user=request.user).order_by("-id")[:50]
        rentals = (
            Rental.objects.filter(user=request.user).select_related("node").order_by("-created_at")[:10]
        )
        return Response({
            "user": UserSerializer(request.user).data,
            "nodes": NodeSerializer(nodes, many=True, context={"request": request}).data,
            "batches": BatchSerializer(batches, many=True).data,
            "rentals": RentalSerializer(rentals, many=True).data,
            "events": EventSerializer(events, many=True).data,
            "tasks": task_catalog(),
            "limits": {
                "kinds": list(AVAILABLE_KINDS),
                "max_file_bytes": settings.MAX_FILE_BYTES,
                "max_batch_files": settings.MAX_BATCH_FILES,
                "max_batch_bytes": settings.MAX_BATCH_BYTES,
                "max_running": request.user.max_running,
                "daily_limit": request.user.daily_limit,
                "rental_max_minutes": settings.RENTAL_MAX_MINUTES,
                "rental_daily_minutes": settings.RENTAL_DAILY_MINUTES,
            },
        })
