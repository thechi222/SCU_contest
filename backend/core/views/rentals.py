"""互動式租借的使用者端點(README §4.10)。"""

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from core import rentals as rental_service
from core.models import Node, Rental
from core.profiles import workspace_catalog
from core.serializers import RentalCreateSerializer, RentalSerializer


class RentalListCreateView(APIView):
    """GET:自己的租借紀錄與目前可租借的設備;POST:提出租借申請。"""

    def get(self, request):
        mine = Rental.objects.filter(user=request.user).select_related("node").order_by("-created_at")[:20]
        available = Node.objects.filter(allow_rental=True, revoked=False, sharing=True).count()
        return Response({
            "rentals": RentalSerializer(mine, many=True).data,
            "workspaces": workspace_catalog(),
            "limits": {
                "max_minutes": settings.RENTAL_MAX_MINUTES,
                "daily_minutes": settings.RENTAL_DAILY_MINUTES,
                "start_seconds": settings.RENTAL_START_SECONDS,
            },
            "nodes_open_to_rental": available,
            "queue_length": Rental.objects.filter(status=Rental.Status.QUEUED).count(),
        })

    def post(self, request):
        data = RentalCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rental = rental_service.request_rental(
            request.user,
            data.validated_data["workspace"],
            data.validated_data["minutes"],
            data.validated_data.get("purpose", ""),
        )
        return Response(RentalSerializer(rental).data, status=201)


class RentalCancelView(APIView):
    """排隊中直接取消;已在設備上則標記結束中,容器於下一次心跳停止。"""

    def post(self, request, rental_id):
        rental = rental_service.cancel_rental(request.user, rental_id)
        return Response(RentalSerializer(rental).data)
