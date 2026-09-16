from rest_framework.views import APIView

from core.permissions import HasAgentToken


class HeartbeatView(APIView):
    authentication_classes = []
    permission_classes = [HasAgentToken]

    def post(self, request):
        """POST /api/agent/heartbeat(AgentHeartbeatSerializer)→ 200 OK"""
        raise NotImplementedError
