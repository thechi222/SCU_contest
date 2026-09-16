"""Fixed input/output paths. A new process and CUDA context for each job."""
import json
import sys
import time
from pathlib import Path

OUT = Path('/output')

def stage(value):
    temporary = OUT / 'stage.tmp'
    temporary.write_text(json.dumps({'stage': value}), encoding='utf-8')
    temporary.replace(OUT / 'stage.json')

def timestamp(seconds):
    ms = max(0, round(seconds * 1000))
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def asr():
    import ctranslate2
    from faster_whisper import WhisperModel
    if ctranslate2.get_cuda_device_count() < 1:
        raise RuntimeError('沒有可用 CUDA 裝置')
    stage('載入模型')
    model = WhisperModel('/models/whisper-small', device='cuda', compute_type='int8_float16', local_files_only=True)
    if model.model.device != 'cuda':
        raise RuntimeError('模型未使用 CUDA')
    stage('GPU 運算中')
    start = time.perf_counter()
    segments, info = model.transcribe('/input/source', beam_size=5, vad_filter=False)
    transcript, subtitles = [], []
    for i, segment in enumerate(segments, 1):
        transcript.append(segment.text.strip())
        subtitles.append(f'{i}\n{timestamp(segment.start)} --> {timestamp(segment.end)}\n{segment.text.strip()}\n')
    elapsed = time.perf_counter() - start
    (OUT/'transcript.txt').write_text('\n'.join(transcript) or '（未辨識到語音）', encoding='utf-8')
    (OUT/'subtitles.srt').write_text('\n'.join(subtitles) or '\n', encoding='utf-8')
    return {'profile':'whisper-small-v1','cuda_verified':True,'gpu_seconds':elapsed,
            'engine':'CTranslate2 '+ctranslate2.__version__,'compute_type':'int8_float16',
            'audio_seconds':info.duration,'language':info.language,'timing':'CUDA inference wall time including decoding'}

def upscale():
    import torch
    import numpy as np
    from PIL import Image, ImageOps
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    if not torch.cuda.is_available():
        raise RuntimeError('沒有可用 CUDA 裝置')
    stage('載入模型')
    network = RRDBNet(num_in_ch=3,num_out_ch=3,num_feat=64,num_block=23,num_grow_ch=32,scale=2)
    runner = RealESRGANer(scale=2,model_path='/models/RealESRGAN_x2plus.pth',model=network,
                         tile=128,tile_pad=10,pre_pad=0,half=True,device=torch.device('cuda:0'))
    if next(runner.model.parameters()).device.type != 'cuda':
        raise RuntimeError('模型未使用 CUDA')
    with Image.open('/input/source') as source:
        # Preserve input geometry; UI and result validation use the same pixels.
        rgb = np.array(source.convert('RGB'))
    stage('GPU 運算中')
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output, _ = runner.enhance(rgb[:,:,::-1], outscale=2)
    torch.cuda.synchronize()
    elapsed = time.perf_counter()-start
    Image.fromarray(output[:,:,::-1]).save(OUT/'upscaled.png')
    return {'profile':'realesrgan-x2-v1','cuda_verified':True,'gpu_seconds':elapsed,'engine':'torch '+torch.__version__,
            'device':torch.cuda.get_device_name(0),'peak_vram_mb':torch.cuda.max_memory_allocated()/1024**2,
            'tile':128,'scale':2,'timing':'synchronized CUDA inference wall time'}

if __name__ == '__main__':
    result = {'asr':asr,'upscale':upscale}[sys.argv[1]]()
    (OUT/'metrics.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
