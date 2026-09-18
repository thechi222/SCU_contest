import tempfile
import zipfile

from django.db import transaction
from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.exceptions import ApiError
from core.models import Batch, Job
from core.profiles import PROFILES
from core.serializers import BatchCreateSerializer, BatchSerializer


class BatchCreateView(APIView):
    """上傳一批檔案。每個檔案成為一件獨立工作,分別排隊與重試。"""

    def post(self, request):
        data = BatchCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data
        services.check_daily_quota(request.user, len(payload["files"]))

        with transaction.atomic():
            batch = Batch.objects.create(
                user=request.user, name=payload["name"], kind=payload["kind"],
            )
            for upload in payload["files"]:
                Job.objects.create(
                    batch=batch, user=request.user, kind=batch.kind, profile=PROFILES[batch.kind],
                    filename=upload.name[:255], input_file=upload, input_bytes=upload.size,
                )
            services.record("batch", f"{batch.name} 已送出 {len(payload['files'])} 個檔案",
                            user=request.user)

        batch.refresh_from_db()
        return Response(BatchSerializer(batch).data, status=201)


class BatchDownloadView(APIView):
    """把整批的成果打包下載。"""

    def get(self, request, batch_id):
        batch = Batch.objects.filter(pk=batch_id, user=request.user).prefetch_related("jobs__artifacts").first()
        if batch is None:
            raise ApiError("找不到這個批次", code="NOT_FOUND", status_code=404)

        archive = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for job in batch.jobs.all():
                for artifact in job.artifacts.all():
                    with artifact.file.open("rb") as content:
                        bundle.writestr(f"{job.filename}/{artifact.name}", content.read())
        archive.seek(0)
        return FileResponse(archive, as_attachment=True, filename=f"{batch.name}.zip")
