from rest_framework.views import APIView

from core.authentication import AgentTokenAuthentication
from core.permissions import HeartbeatMachineMatches, IsAgent


class AgentAPIView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [IsAgent]


class HeartbeatView(AgentAPIView):
    permission_classes = [IsAgent, HeartbeatMachineMatches]

    def post(self, request):
        """POST /api/agent/heartbeat(AgentHeartbeatSerializer)→ 200 OK
        寫入心跳並更新機台狀態:owner_active 為 true 時轉為 busy,否則 offline / busy 轉回 idle。"""
        raise NotImplementedError


class TaskClaimView(AgentAPIView):
    def post(self, request):
        """POST /api/agent/tasks/claim → AgentTaskSerializer;無待辦任務時回 204
        取出 request.auth 機台最早的 pending 任務並改為 claimed。"""
        raise NotImplementedError


class TaskResultView(AgentAPIView):
    def post(self, request, task_id):
        """POST /api/agent/tasks/{id}/result(AgentTaskResultSerializer)→ 200 OK
        start 成功:寫入 access_url,預約轉 active、機台轉 rented;start 失敗:預約轉 failed。
        stop 成功:預約轉 done、機台轉 idle。非本機台的任務回 404。"""
        raise NotImplementedError
