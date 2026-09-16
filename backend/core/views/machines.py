from rest_framework.permissions import AllowAny
from rest_framework.views import APIView


class MachineListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """GET /api/machines → MachineSerializer[]"""
        raise NotImplementedError


class MachineMetricsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, machine_id):
        """GET /api/machines/{id}/metrics → AgentHeartbeatSerializer[](最近 60 筆,由舊到新)"""
        raise NotImplementedError
