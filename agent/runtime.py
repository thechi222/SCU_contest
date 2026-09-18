"""Only pretested, immutable local image IDs may be started by the agent."""
import json
import os
import re
import threading
import time
from pathlib import Path
from .hardware import docker

class Cancelled(Exception):
    pass

def cleanup_owned(owner_id):
    if not re.fullmatch(r'[a-f0-9]{32}',owner_id):
        raise ValueError('設備識別不正確')
    names=docker(['ps','-a','--filter','label=relay-owner='+owner_id,'--format','{{.Names}}']).stdout.splitlines()
    for name in names:
        if not re.fullmatch(r'relay-[a-f0-9]{32}',name):
            raise RuntimeError('發現不符合格式的設備容器，請檢查本機環境')
        docker(['rm','-f',name],timeout=5)

class Runner:
    def __init__(self, gpu_uuid, profiles, owner_id=None):
        self.gpu_uuid, self.profiles = gpu_uuid, profiles
        self.owner_id=owner_id
        self.lock = threading.Lock()
        self.name = None

    def stop(self):
        with self.lock:
            name = self.name
        if name:
            # Scoped to this exact agent container; never reset the whole GPU.
            docker(['rm','-f',name],timeout=5,check=False)

    def execute(self, kind, job_dir, cancelled, update=lambda value: None):
        profile = self.profiles[kind]
        image_id = profile['image_id']
        if not re.fullmatch(r'sha256:[a-f0-9]{64}',image_id):
            raise ValueError('容器映像尚未固定，請先執行 prepare')
        root=Path(job_dir).resolve(); output=root/'output'; output.mkdir(exist_ok=True)
        if os.name != 'nt': output.chmod(0o777)
        models=Path(profile['models']).resolve()
        name='relay-'+root.name
        if not re.fullmatch(r'relay-[a-f0-9]{32}',name):
            raise ValueError('工作識別不正確')
        user_args=[] if os.name=='nt' else ['--user',f'{os.getuid()}:{os.getgid()}']
        args=['create','--name',name,'--label','campus-relay=worker','--gpus','device='+self.gpu_uuid,
              '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
              '--pids-limit','256','--cpus','4','--memory','6g','--shm-size','256m',
              '--tmpfs','/tmp:rw,nosuid,size=256m','--env','HOME=/tmp',*user_args,
              '--mount',f'type=bind,src={root / "source"},dst=/input/source,readonly',
              '--mount',f'type=bind,src={output},dst=/output',
              '--mount',f'type=bind,src={models},dst=/models,readonly',image_id]
        if self.owner_id:
            args[1:1]=['--label','relay-owner='+self.owner_id]
        with self.lock:
            if cancelled.is_set(): raise Cancelled()
            self.name=name
        try:
            docker(args,timeout=20)
            if cancelled.is_set(): raise Cancelled()
            docker(['start',name],timeout=10)
            deadline=time.monotonic()+1800
            while True:
                if cancelled.wait(.5): raise Cancelled()
                if time.monotonic()>deadline: raise RuntimeError('工作超過 30 分鐘，已停止')
                if (output/'stage.json').is_file():
                    try: update(json.loads((output/'stage.json').read_text('utf-8'))['stage'])
                    except (ValueError,OSError,KeyError): pass
                status=json.loads(docker(['inspect','--format','{{json .State}}',name],timeout=5).stdout)
                if not status['Running']:
                    if status['ExitCode']:
                        log=docker(['logs','--tail','20',name],check=False).stderr
                        (root/'error.log').write_text(log,encoding='utf-8')
                        raise RuntimeError('GPU 工作失敗：'+('顯示或系統記憶體不足' if status.get('OOMKilled') or 'out of memory' in log.lower() else log.strip().splitlines()[-1][:200] if log.strip() else '請查看本機 error.log'))
                    break
            if cancelled.is_set(): raise Cancelled()
            metrics=json.loads((output/'metrics.json').read_text('utf-8'))
            if metrics.get('cuda_verified') is not True or metrics.get('profile')!=profile['profile']:
                raise RuntimeError('缺少真實 CUDA 執行證據')
            metrics.update(image_id=image_id,gpu_uuid=self.gpu_uuid,model_manifest=profile['manifest_sha256'])
            return metrics
        finally:
            try: self.stop()
            finally:
                with self.lock: self.name=None
