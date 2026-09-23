from rest_framework.permissions import BasePermission

from core.models import Node


class IsNode(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Node)


class IsPlatformAdmin(BasePermission):
    """管理台限管理員使用(README §4.12)。"""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
