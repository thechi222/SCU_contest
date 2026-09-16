from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler


class ApiError(exceptions.APIException):
    def __init__(self, detail: str, code: str, status_code: int = 400):
        super().__init__(detail=detail, code=code)
        self.status_code = status_code


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None

    codes = exc.get_codes()
    code = codes.upper() if isinstance(codes, str) else "VALIDATION_ERROR"
    data = response.data
    detail = data.get("detail", data) if isinstance(data, dict) else data
    response.data = {"detail": detail, "code": code}
    return response
