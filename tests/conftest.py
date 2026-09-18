from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from core.authentication import hash_token
from core.models import Batch, Job, Node, User
from core.profiles import PROFILES

NODE_TOKEN = "node-token-for-tests"


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "data"
    return settings.MEDIA_ROOT


@pytest.fixture
def make_user(db):
    def factory(email="tester@scu.edu.tw", role="student", **fields):
        return User.objects.create_user(
            username=email, email=email, name=email.split("@")[0], role=role,
            password="unused-password", **fields,
        )
    return factory


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def make_node(db, make_user):
    def factory(owner=None, token=NODE_TOKEN, kinds=("asr",), **fields):
        owner = owner or make_user(email=f"owner-{token[:6]}@scu.edu.tw", role="staff")
        defaults = {"sharing": True, "local_enabled": True}
        return Node.objects.create(
            owner=owner, name=f"node-{token[:6]}", token_hash=hash_token(token),
            gpu_uuid=f"GPU-{token[:8]}", gpu_name="RTX 3050", memory_mb=8192,
            capabilities={kind: {"profile": PROFILES[kind], "cuda_verified": True, "peak_vram_mb": 2048}
                          for kind in kinds},
            **{**defaults, **fields},
        )
    return factory


@pytest.fixture
def node(make_node):
    return make_node()


@pytest.fixture
def make_job(db):
    def factory(owner, kind="asr", filename="sample.wav", **fields):
        batch = Batch.objects.create(user=owner, name="批次", kind=kind)
        return Job.objects.create(
            batch=batch, user=owner, kind=kind, profile=PROFILES[kind], filename=filename,
            input_file=SimpleUploadedFile(filename, b"input-bytes"), input_bytes=11, **fields,
        )
    return factory


@pytest.fixture
def expire_lease():
    """把 attempt 的租約改到過去,模擬節點失聯。"""
    def apply(attempt):
        attempt.lease_until = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=["lease_until"])
    return apply
