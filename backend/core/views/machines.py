from rest_framework.views import APIView


class MachineListView(APIView):
    def get(self, request):
        """GET /api/machines → MachineSerializer[]"""
        raise NotImplementedError


class MachineAvailabilityView(APIView):
    def get(self, request, machine_id):
        """GET /api/machines/{id}/availability → AvailabilityWindowSerializer[](尚未結束者,由早到晚)"""
        raise NotImplementedError


class MachineMetricsView(APIView):
    def get(self, request, machine_id):
        """GET /api/machines/{id}/metrics → AgentHeartbeatSerializer[](最近 60 筆,由舊到新)"""
        raise NotImplementedError
