"""Online preparation and real CUDA self-test; no model downloads during jobs."""
import hashlib
import json
import shutil
import threading
import time
import uuid
import wave
from pathlib import Path
import httpx
from PIL import Image, ImageDraw
from .profiles import PROFILES
from .hardware import gpu, telemetry, docker
from .runtime import Runner

ROOT = Path(__file__).resolve().parent.parent

def checksum(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.partial')
    with httpx.stream('GET',url,follow_redirects=True,timeout=120) as response:
        response.raise_for_status()
        with temporary.open('wb') as f:
            for data in response.iter_bytes(1024*1024):f.write(data)
    temporary.replace(path)

def verify_profiles(profiles,hardware):
    for kind, profile in profiles.items():
        if profile['gpu_uuid']!=hardware['gpu_uuid'] or profile['driver']!=hardware['driver']:
            raise RuntimeError('GPU 或驅動已變更，請重新 prepare 與實測')
        manifest=Path(profile['models'])/'manifest.json'
        if checksum(manifest)!=profile['manifest_sha256']:
            raise RuntimeError('模型版本紀錄已改變，請重新 prepare')
        for relative,digest in json.loads(manifest.read_text('utf-8'))['files'].items():
            if checksum(manifest.parent/relative)!=digest:
                raise RuntimeError('模型內容與準備紀錄不符')
        if docker(['image','inspect','--format','{{.Id}}',profile['image_id']]).stdout.strip()!=profile['image_id']:
            raise RuntimeError('已測試的容器映像不存在')

def prepare(directory,index,kinds,build=True):
    directory=Path(directory).resolve(); directory.mkdir(parents=True,exist_ok=True)
    hardware=gpu(index)
    docker(['info','--format','{{.ServerVersion}}'],timeout=20)
    target=directory/'profiles.json'
    profiles=json.loads(target.read_text('utf-8')) if target.exists() else {}
    for kind in kinds:
        print('Preparing '+kind,flush=True)
        tag='campus-relay/'+kind+':v1'
        if build:
            docker(['build','-f',str(ROOT/'workers'/f'{kind}.Dockerfile'),'-t',tag,str(ROOT)],timeout=3600)
        image_id=docker(['image','inspect','--format','{{.Id}}',tag]).stdout.strip()
        model_dir=directory/'models'/kind; model_dir.mkdir(parents=True,exist_ok=True)
        manifest_path=model_dir/'manifest.json'
        # Existing weights are reused only when their entire manifest verifies.
        valid=False
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text('utf-8'))
            valid=all((model_dir/p).is_file() and checksum(model_dir/p)==s for p,s in manifest['files'].items())
        if not valid:
            if kind=='asr':
                revision=json.loads((ROOT/'workers'/'models.json').read_text('utf-8'))['whisper_revision']
                for name in ('config.json','model.bin','tokenizer.json','vocabulary.txt'):
                    download(f'https://huggingface.co/Systran/faster-whisper-small/resolve/{revision}/{name}',model_dir/'whisper-small'/name)
                source='Systran/faster-whisper-small@'+revision
            else:
                source='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth'
                download(source,model_dir/'RealESRGAN_x2plus.pth')
            files={p.relative_to(model_dir).as_posix():checksum(p) for p in model_dir.rglob('*') if p.is_file() and p.name!='manifest.json'}
            manifest_path.write_text(json.dumps({'source':source,'files':files},indent=2),encoding='utf-8')
        profile={'profile':PROFILES[kind],'image_id':image_id,'models':str(model_dir),
                 'gpu_uuid':hardware['gpu_uuid'],'driver':hardware['driver'],'manifest_sha256':checksum(manifest_path)}
        folder=directory/'checks'/uuid.uuid4().hex; folder.mkdir(parents=True)
        if kind=='asr':
            # Silence tests CUDA execution, not transcription quality.
            with wave.open(str(folder/'source'),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*16000*3)
        else:
            image=Image.new('RGB',(128,96),'#254f50');draw=ImageDraw.Draw(image)
            for x in range(0,128,8):draw.line((x,0,128-x,95),fill='#caf38e',width=2)
            image.save(folder/'source',format='PNG')
        stop=threading.Event(); peaks=[]
        def sample():
            while not stop.wait(.2):
                value=telemetry(index).get('memory_used_mb')
                if value is not None:peaks.append(value)
        sampler=threading.Thread(target=sample,daemon=True);sampler.start()
        try:
            metrics=Runner(hardware['gpu_uuid'],{kind:profile}).execute(kind,folder,threading.Event())
        finally:stop.set();sampler.join(2)
        profile['peak_vram_mb']=round(max(peaks or [metrics.get('peak_vram_mb',0)])+384)
        if profile['peak_vram_mb']<=384:raise RuntimeError('無法量測 GPU 記憶體，尚不登錄此服務')
        profile.update(cuda_verified=True,tested_at=time.time(),self_test=metrics)
        profiles[kind]=profile
        target.write_text(json.dumps(profiles,ensure_ascii=False,indent=2),encoding='utf-8')
        print(kind+' CUDA test passed. Peak + reserve: '+str(profile['peak_vram_mb'])+' MB',flush=True)
    return profiles
