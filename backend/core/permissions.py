from rest_framework.permissions import BasePermission

from core.models import Node


class IsNode(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, Node)
