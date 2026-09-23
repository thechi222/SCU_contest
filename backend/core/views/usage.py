"""閒置算力儀表板的端點(README §4.9)。"""

import csv

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from core import usage
from core.exceptions import ApiError
from core.models import Node

MAX_SERIES_HOURS = 72
MAX_EXPORT_DAYS = 365


def _int_param(request, name, default, maximum):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(f"{name} 必須是整數", code="VALIDATION_ERROR", status_code=400) from None
    if not 1 <= value <= maximum:
        raise ApiError(f"{name} 需介於 1 與 {maximum} 之間", code="VALIDATION_ERROR", status_code=400)
    return value


class UsageSummaryView(APIView):
    """儀表板主要來源:平台總覽、各機台狀態與曲線、每日用量。前端每 5 秒輪詢一次。"""

    def get(self, request):
        hours = _int_param(request, "hours", None, MAX_SERIES_HOURS)
        return Response(usage.overview(request.user, hours=hours))


class UsageNodeView(APIView):
    """單一機台的取樣序列,供儀表板展開細節使用。"""

    def get(self, request, node_id):
        node = Node.objects.filter(pk=node_id, revoked=False).select_related("owner").first()
        if node is None:
            raise ApiError("找不到這台設備", code="NOT_FOUND", status_code=404)
        hours = _int_param(request, "hours", None, MAX_SERIES_HOURS)
        return Response({
            "node": {
                "id": str(node.id), "name": node.name, "gpu_name": node.gpu_name,
                "memory_mb": node.memory_mb, "owner_name": node.owner.name,
                "is_mine": node.owner_id == request.user.id,
                "state": usage.current_state(node), "last_seen": node.last_seen,
            },
            "series": usage.series([node], hours=hours)[node.id],
        })


class UsageExportView(APIView):
    """把每日用量彙整匯出成 CSV,供保存與後續分析。"""

    def get(self, request):
        days = _int_param(request, "days", 30, MAX_EXPORT_DAYS)
        node = None
        node_id = request.query_params.get("node")
        if node_id:
            node = Node.objects.filter(pk=node_id).first()
            if node is None:
                raise ApiError("找不到這台設備", code="NOT_FOUND", status_code=404)

        writer = csv.writer(Echo())
        response = StreamingHttpResponse(
            (writer.writerow(row) for row in usage.export_rows(days=days, node=node)),
            content_type="text/csv; charset=utf-8",
        )
        filename = f"powershare-usage-{timezone.localdate().isoformat()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class Echo:
    """csv.writer 需要有 write() 的物件;串流輸出時直接把該列字串交出去。"""

    def write(self, value):
        return value
