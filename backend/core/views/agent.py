import json

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import rentals as rental_service
from core import services, usage
from core.authentication import NodeTokenAuthentication, hash_token, new_token
from core.exceptions import ApiError
from core.models import Artifact, Attempt, Node, PairingCode
from core.permissions import IsNode
from core.profiles import ARTIFACT_NAMES, WORKSPACES
from core.serializers import (
    AssignmentSerializer, AttemptFailSerializer, HeartbeatResponseSerializer,
    HeartbeatSerializer, PairSerializer, RentalAssignmentSerializer,
    RentalEndedSerializer, RentalReadySerializer,
)


class AgentAPIView(APIView):
    authentication_classes = [NodeTokenAuthentication]
    permission_classes = [IsNode]


class PairView(APIView):
    """以一次性配對碼登錄節點,回傳只顯示一次的節點 token。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = PairSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data

        code = PairingCode.objects.filter(
            code_hash=hash_token(payload["code"]), used_at__isnull=True, expires_at__gt=timezone.now(),
        ).select_related("owner").first()
        if code is None:
            raise ApiError("配對碼無效或已過期", code="PAIRING_CODE_INVALID", status_code=403)
        if Node.objects.filter(gpu_uuid=payload["gpu_uuid"]).exists():
            raise ApiError("這張 GPU 已經登錄過", code="NODE_EXISTS", status_code=409)

        token = new_token()
        node = Node.objects.create(
            owner=code.owner, name=payload["name"], token_hash=hash_token(token),
            gpu_uuid=payload["gpu_uuid"], gpu_name=payload["gpu_name"], memory_mb=payload["memory_mb"],
            capabilities=payload["capabilities"], environment=payload.get("environment", {}),
        )
        code.used_at = timezone.now()
        code.save(update_fields=["used_at"])
        services.record("node", f"{node.name} 已完成配對", user=code.owner, node=node)
        return Response({"node_id": str(node.id), "token": token})


class HeartbeatView(AgentAPIView):
    """每 5 秒一次:更新節點狀態並續約。stop 為 true 時 Agent 立即停止容器。

    Agent 帶 `attempt_id` 代表正在執行工作,帶 `rental_id` 代表正在提供互動式租借;
    `stop` 針對本次回報的那一項。同時也依取樣間隔留存一筆用量紀錄(§4.9)。
    """

    def post(self, request):
        data = HeartbeatSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        payload = data.validated_data
        node: Node = request.auth

        node.local_enabled = payload["local_enabled"]
        node.telemetry = payload.get("telemetry") or {}
        node.last_seen = timezone.now()
        if payload.get("capabilities"):
            node.capabilities = payload["capabilities"]
        if payload.get("environment"):
            node.environment = payload["environment"]
        node.save(update_fields=["local_enabled", "telemetry", "last_seen", "capabilities", "environment"])

        stop = False
        if payload.get("attempt_id"):
            stop = not services.renew_lease(
                node, payload["attempt_id"], payload.get("stage"), payload.get("progress"),
            )
        elif payload.get("rental_id"):
            stop = not rental_service.renew_lease(node, payload["rental_id"])

        usage.record_sample(
            node,
            has_attempt=bool(payload.get("attempt_id")) and not stop,
            has_rental=bool(payload.get("rental_id")) and not stop,
        )
        body = {
            "stop": stop,
            "lease_seconds": settings.LEASE_SECONDS,
            "sharing": node.sharing and not node.revoked,
            "within_schedule": services.within_schedule(node),
        }
        return Response(HeartbeatResponseSerializer(body).data)


class ClaimView(AgentAPIView):
    """領取一件工作;沒有合適工作時 assignment 為 null。"""

    def post(self, request):
        attempt = services.claim_job(request.auth)
        if attempt is None:
            return Response({"assignment": None})

        job = attempt.job
        assignment = {
            "attempt_id": attempt.id,
            "job_id": job.id,
            "kind": job.kind,
            "profile": job.profile,
            "input_url": f"/api/agent/attempts/{attempt.id}/input",
            "input_bytes": job.input_bytes,
            "lease_seconds": settings.LEASE_SECONDS,
        }
        return Response({"assignment": AssignmentSerializer(assignment).data})


def active_attempt_or_404(node: Node, attempt_id) -> Attempt:
    attempt = (
        Attempt.objects.filter(pk=attempt_id, node=node, ended_at__isnull=True)
        .select_related("job").first()
    )
    if attempt is None:
        raise ApiError("這次執行已結束", code="ATTEMPT_NOT_ACTIVE", status_code=409)
    return attempt


class AttemptInputView(AgentAPIView):
    def get(self, request, attempt_id):
        attempt = active_attempt_or_404(request.auth, attempt_id)
        return FileResponse(attempt.job.input_file.open("rb"), as_attachment=True, filename="source")


class AttemptCompleteView(AgentAPIView):
    """接收成果檔案與量測數據。只接受仍持有租約的 attempt,逾時後的結果一律拒絕。"""

    def post(self, request, attempt_id):
        attempt = active_attempt_or_404(request.auth, attempt_id)
        expected = ARTIFACT_NAMES[attempt.job.kind]
        uploads = request.FILES.getlist("files")
        if sorted(upload.name for upload in uploads) != sorted(expected):
            raise ApiError(f"成果檔案應為 {expected}", code="ARTIFACT_MISMATCH", status_code=400)

        try:
            metrics = json.loads(request.data.get("metrics") or "{}")
        except ValueError:
            raise ApiError("量測數據格式不正確", code="VALIDATION_ERROR", status_code=400) from None
        if not isinstance(metrics, dict) or len(json.dumps(metrics)) > 8192:
            raise ApiError("量測數據格式不正確", code="VALIDATION_ERROR", status_code=400)

        artifacts = [
            Artifact(
                name=upload.name, file=upload, size=upload.size,
                media_type=upload.content_type or "application/octet-stream",
            )
            for upload in uploads
        ]
        services.complete_attempt(request.auth, attempt_id, artifacts, metrics)
        return Response({"status": "ok"})


class AttemptFailView(AgentAPIView):
    def post(self, request, attempt_id):
        data = AttemptFailSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.fail_attempt(request.auth, attempt_id, data.validated_data["reason"])
        return Response({"status": "ok"})


class RentalClaimView(AgentAPIView):
    """領取一段互動式租借;沒有合適的申請時 rental 為 null。"""

    def post(self, request):
        rental = rental_service.claim_rental(request.auth)
        if rental is None:
            return Response({"rental": None})

        profile = WORKSPACES.get(rental.workspace, {})
        assignment = {
            "rental_id": rental.id,
            "workspace": rental.workspace,
            "image": rental.image,
            "entry": profile.get("entry", "shell"),
            "minutes": rental.minutes,
            "lease_seconds": settings.LEASE_SECONDS,
        }
        return Response({"rental": RentalAssignmentSerializer(assignment).data})


class RentalReadyView(AgentAPIView):
    """容器啟動且連線通道備妥後回報。租借時數自平台收到本次回報起算。"""

    def post(self, request, rental_id):
        data = RentalReadySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rental = rental_service.mark_ready(
            request.auth, rental_id,
            data.validated_data["connect_url"],
            data.validated_data.get("connect_token", ""),
            data.validated_data.get("connection", {}),
        )
        return Response({"status": "ok", "expires_at": rental.expires_at})


class RentalEndedView(AgentAPIView):
    """容器已停止。啟動階段失敗回報為 failed,其餘視為正常結束。"""

    def post(self, request, rental_id):
        data = RentalEndedSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rental_service.agent_ended(request.auth, rental_id, data.validated_data.get("reason", ""))
        return Response({"status": "ok"})
