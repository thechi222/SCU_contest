from dataclasses import dataclass, field
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
PROFILES = {'asr': 'whisper-small-v1', 'upscale': 'realesrgan-x2-v1'}
ACTIVE = ('loading', 'running')
PENDING = ('queued', 'retrying')
TERMINAL = ('completed', 'failed', 'cancelled')

@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('RELAY_DATA_DIR', ROOT / 'data')).resolve())
    frontend_dir: Path = field(default_factory=lambda: ROOT / 'frontend' / 'dist')
    lease_seconds: float = 20.0
    heartbeat_seconds: float = 5.0
    secure_cookies: bool = field(default_factory=lambda: os.getenv('RELAY_SECURE_COOKIES', '0') == '1')
    session_seconds: int = 8 * 3600
    max_file_bytes: int = 50 * 1024 * 1024
    max_batch_files: int = 20
    max_storage_bytes: int = 10 * 1024 * 1024 * 1024
    allowed_hosts: list[str] = field(default_factory=lambda: os.getenv('RELAY_ALLOWED_HOSTS', '127.0.0.1,localhost,testserver').split(','))
    test_mode: bool = False

