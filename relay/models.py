from typing import Literal
import json
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from .config import PROFILES

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Login(StrictModel):
    username: str = Field(min_length=1,max_length=50)
    password: str = Field(min_length=1,max_length=200)

class UserCreate(StrictModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,40}$')
    display_name: str = Field(min_length=1,max_length=60)
    password: str = Field(min_length=12,max_length=200)
    role: Literal['member','admin'] = 'member'

class UserUpdate(StrictModel):
    enabled: bool | None = None
    max_running: int | None = Field(default=None,ge=1,le=8)
    daily_limit: int | None = Field(default=None,ge=1,le=1000)

class PasswordChange(StrictModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=12,max_length=200)

def validate_capabilities(value):
    if not isinstance(value,dict) or not set(value)<=set(PROFILES):
        raise ValueError('未知的任務能力')
    for kind, cap in value.items():
        if not isinstance(cap,dict) or set(cap)-{'profile','cuda_verified','peak_vram_mb'}:
            raise ValueError('能力格式不正確')
        if cap.get('profile')!=PROFILES[kind] or cap.get('cuda_verified') is not True:
            raise ValueError('任務必須先通過 GPU 自我測試')
        peak=cap.get('peak_vram_mb')
        if not isinstance(peak,(float,int)) or isinstance(peak,bool) or not 0<peak<1000000:
            raise ValueError('顯示記憶體測試數據不正確')
    return value

class Pair(StrictModel):
    code: str = Field(min_length=8,max_length=64)
    name: str = Field(min_length=1,max_length=60)
    gpu_uuid: str = Field(min_length=5,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    gpu_name: str = Field(min_length=1,max_length=120)
    memory_mb: int = Field(gt=0,lt=1000000)
    capabilities: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)
    _caps = field_validator('capabilities')(validate_capabilities)

    @field_validator('environment')
    @classmethod
    def bounded_environment(cls,v):
        if len(json.dumps(v))>8192:
            raise ValueError('環境回報過大')
        return v

class Heartbeat(StrictModel):
    attempt_id: str | None = Field(default=None,max_length=40)
    local_enabled: bool = False
    capabilities: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)
    telemetry: dict = Field(default_factory=dict)
    stage: Literal['下載輸入','載入模型','GPU 運算中','上傳結果'] | None = None
    progress: float | None = Field(default=None,ge=0,le=1)
    _caps=field_validator('capabilities')(validate_capabilities)
    _environment=field_validator('environment')(Pair.bounded_environment.__func__)

    @field_validator('telemetry')
    @classmethod
    def bounded_telemetry(cls,v):
        allowed={'gpu_utilization','memory_used_mb','memory_free_mb','temperature_c','power_w','on_ac','gpu_name'}
        if set(v)-allowed:
            raise ValueError('未知的監控欄位')
        for k in ('gpu_utilization','memory_used_mb','memory_free_mb','temperature_c','power_w'):
            n=v.get(k)
            if n is not None and (isinstance(n,bool) or not isinstance(n,(int,float)) or not 0<=n<1000000):
                raise ValueError('監控數值不正確')
        if v.get('on_ac') is not None and not isinstance(v['on_ac'],bool):
            raise ValueError('電源狀態不正確')
        if v.get('gpu_name') is not None and (not isinstance(v['gpu_name'],str) or len(v['gpu_name'])>120):
            raise ValueError('GPU 名稱不正確')
        return v

class NodeUpdate(StrictModel):
    name: str | None = Field(default=None,min_length=1,max_length=60)
    sharing: bool | None = None
    revoked: bool | None = None
    schedule_start: str | None = Field(default=None,pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    schedule_end: str | None = Field(default=None,pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    utc_offset_minutes: int | None = Field(default=None,ge=-720,le=840)

class Failure(StrictModel):
    reason: str = Field(min_length=1,max_length=400)

class ResetDemo(StrictModel):
    batch_ids: list[str] = Field(min_length=1,max_length=100)
    confirmation: Literal['RESET DEMO']

