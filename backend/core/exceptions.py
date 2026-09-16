from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, JsonResponse
from django.views import defaults
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


def _is_api_request(request) -> bool:
    return request.path.startswith("/api/")


def api_not_found(request, exception):
    if _is_api_request(request):
        return JsonResponse({"detail": "找不到資源", "code": "NOT_FOUND"}, status=404)
    return defaults.page_not_found(request, exception)


def api_server_error(request):
    if _is_api_request(request):
        return JsonResponse({"detail": "伺服器發生錯誤", "code": "SERVER_ERROR"}, status=500)
    return defaults.server_error(request)
