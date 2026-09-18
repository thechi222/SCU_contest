from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from core import services
from core.exceptions import ApiError
from core.models import Artifact, Job
from core.serializers import JobSerializer


def own_job_or_404(user, job_id) -> Job:
    job = Job.objects.filter(pk=job_id, user=user).first()
    if job is None:
        raise ApiError("找不到這件工作", code="NOT_FOUND", status_code=404)
    return job


class JobCancelView(APIView):
    def post(self, request, job_id):
        return Response(JobSerializer(services.cancel_job(request.user, job_id)).data)


class JobRetryView(APIView):
    def post(self, request, job_id):
        return Response(JobSerializer(services.retry_job(request.user, job_id)).data)


class JobInputView(APIView):
    def get(self, request, job_id):
        job = own_job_or_404(request.user, job_id)
        return FileResponse(job.input_file.open("rb"), as_attachment=True, filename=job.filename)


class ArtifactDownloadView(APIView):
    def get(self, request, artifact_id):
        artifact = Artifact.objects.filter(pk=artifact_id, job__user=request.user).first()
        if artifact is None:
            raise ApiError("找不到這個檔案", code="NOT_FOUND", status_code=404)
        return FileResponse(
            artifact.file.open("rb"), as_attachment=True, filename=artifact.name,
            content_type=artifact.media_type,
        )
