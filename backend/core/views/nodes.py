from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.authentication import hash_token, new_pairing_code
from core.exceptions import ApiError
from core.models import Node, PairingCode
from core.serializers import NodeSerializer, NodeUpdateSerializer

PAIRING_CODE_MINUTES = 10


class PairingCodeView(APIView):
    """產生一次性配對碼,只顯示一次,10 分鐘內有效。"""

    def post(self, request):
        code = new_pairing_code()
        expires_at = timezone.now() + timedelta(minutes=PAIRING_CODE_MINUTES)
        PairingCode.objects.create(
            code_hash=hash_token(code), owner=request.user, expires_at=expires_at,
        )
        return Response({"code": code, "expires_at": expires_at})


class NodeDetailView(APIView):
    """機主調整自己的設備:名稱、分享開關、每日開放時段,或撤銷設備。"""

    def patch(self, request, node_id):
        node = Node.objects.filter(pk=node_id, owner=request.user).first()
        if node is None:
            raise ApiError("找不到這台設備", code="NOT_FOUND", status_code=404)

        data = NodeUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        for field, value in data.validated_data.items():
            setattr(node, field, value)
        node.save()

        if data.validated_data.get("revoked"):
            services.record("node", f"{node.name} 已撤銷", user=request.user, node=node)
        elif "sharing" in data.validated_data:
            state = "開啟" if node.sharing else "關閉"
            services.record("node", f"{node.name} 分享{state}", user=request.user, node=node)
        return Response(NodeSerializer(node, context={"request": request}).data)
