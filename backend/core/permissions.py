from rest_framework.permissions import BasePermission

from core.models import Machine


class IsAgent(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Machine)


class HeartbeatMachineMatches(BasePermission):
    message = "machine_id 與 Agent token 所屬機台不符"

    def has_permission(self, request, view):
        data = request.data
        return isinstance(data, dict) and data.get("machine_id") == request.auth.pk
