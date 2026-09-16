"""Opt-in real GPU demo validation on this host. Creates only labelled demo batches."""
import argparse
import json
import logging
import re
import threading
import time
from pathlib import Path
import httpx
from PIL import Image
from agent.main import Agent
from agent.hardware import gpu,telemetry,docker

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--kind',choices=['asr','upscale','all'],default='all')
    parser.add_argument('--off-test',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    profiles=json.loads((ROOT/'.agent/profiles.json').read_text('utf-8'))
    kinds=['asr','upscale'] if args.kind=='all' else [args.kind]
    if not all(k in profiles for k in kinds):raise RuntimeError('請先通過對應 prepare')
    # Read local initial credentials without logging or putting them in argv.
    accounts=(ROOT/'data/initial-accounts.md').read_text('utf-8')
    def connect(username):
        password=re.search(r'\| '+username+r' \|[^\n]+`([^`]+)`',accounts).group(1)
        c=httpx.Client(base_url='http://127.0.0.1:8765',headers={'X-Relay-Request':'1'},timeout=120,trust_env=False)
        r=c.post('/api/auth/login',json={'username':username,'password':password});r.raise_for_status();return c
    provider=connect('provider');requester=connect('provider')
    directory=ROOT/'.agent';config_file=directory/'config.json';hw=gpu(0)
    if config_file.exists():config=json.loads(config_file.read_text('utf-8'))
    else:
        code=provider.post('/api/pairing-codes').json()['code']
        response=provider.post('/api/agent/pair',json={'code':code,'name':'實機 RTX 3050 筆電',**{k:hw[k] for k in ('gpu_uuid','gpu_name','memory_mb')},
            'capabilities':{k:{n:p[n] for n in ('profile','cuda_verified','peak_vram_mb')} for k,p in profiles.items()},'environment':hw})
        response.raise_for_status();config={**response.json(),'server':'http://127.0.0.1:8765','gpu':0,'ca':None}
        config_file.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');config_file.chmod(0o600)
    agent=Agent(directory,config,profiles)
    (directory/'ENABLED').touch()
    r=provider.patch('/api/nodes/'+config['node_id'],json={'sharing':True});r.raise_for_status()
    runner=threading.Thread(target=agent.run,daemon=True);runner.start()
    results=[]
    def submit(kind,path,label):
        with path.open('rb') as f:
            r=requester.post('/api/batches',data={'kind':kind,'name':label,'is_demo':'true'},files={'files':(path.name,f)})
        r.raise_for_status();return r.json()['job_ids'][0]
    def job(job_id):
        r=requester.get('/api/state');r.raise_for_status()
        return next(j for j in r.json()['jobs'] if j['id']==job_id)
    def complete(job_id,start):
        deadline=time.monotonic()+900;previous=None
        while time.monotonic()<deadline:
            j=job(job_id)
            key=(j['status'],j['stage'],j['attempt_count'])
            if key!=previous:print(j['kind'],key,flush=True);previous=key
            if j['status'] in ('failed','cancelled'):raise RuntimeError(j['error'] or j['stage'])
            if j['status']=='completed':
                out=ROOT/'data'/'verified-results'/job_id;out.mkdir(parents=True,exist_ok=True)
                for artifact in j['artifacts']:
                    r=requester.get('/api/artifacts/'+artifact['id']);r.raise_for_status();(out/artifact['name']).write_bytes(r.content)
                j['elapsed_including_download_seconds']=time.perf_counter()-start
                return j
            time.sleep(1)
        raise TimeoutError('實機工作等待逾時')
    try:
        for kind in kinds:
            path=ROOT/'demo-assets'/('introduction.wav' if kind=='asr' else 'calibration.png')
            start=time.perf_counter();job_id=submit(kind,path,'單機 CUDA 驗證 · '+kind)
            result=complete(job_id,start);results.append(result)
            print('REAL GPU COMPLETE',kind,round(result['elapsed_including_download_seconds'],2),flush=True)
        if args.off_test:
            if 'upscale' not in profiles:raise RuntimeError('OFF 測試需已準備的圖片服務')
            path=ROOT/'data'/'off-test.png'
            with Image.open(ROOT/'demo-assets/calibration.png') as source:source.resize((1536,1024)).save(path)
            baseline=telemetry(0).get('memory_used_mb')
            start=time.perf_counter();job_id=submit('upscale',path,'實機 OFF 與重試驗證')
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                j=job(job_id)
                if j['stage']=='GPU 運算中':break
                if j['status'] in ('completed','failed'):raise RuntimeError('未捕捉到運算階段，需調整示範素材')
                time.sleep(.5)
            else:raise TimeoutError('未進入 GPU 運算階段')
            peak=telemetry(0).get('memory_used_mb');off_start=time.perf_counter()
            provider.patch('/api/nodes/'+config['node_id'],json={'sharing':False}).raise_for_status()
            deadline=time.monotonic()+20
            released=None
            while time.monotonic()<deadline:
                running=docker(['ps','--filter','label=relay-owner='+config['node_id'],'--format','{{.Names}}']).stdout.strip()
                memory=telemetry(0).get('memory_used_mb')
                if not running and baseline is not None and memory is not None and memory<=baseline+128:
                    released=time.perf_counter()-off_start;break
                time.sleep(.25)
            if released is None:raise RuntimeError('未在 20 秒內確認工作容器停止與 GPU 記憶體下降')
            if job(job_id)['status']!='retrying':raise RuntimeError('OFF 後未重新排隊')
            print('OFF released GPU in',round(released,2),'seconds',flush=True)
            provider.patch('/api/nodes/'+config['node_id'],json={'sharing':True}).raise_for_status()
            result=complete(job_id,start)
            result.update(off_release_seconds=released,baseline_vram_mb=baseline,peak_vram_mb=peak,recovery_scope='same physical GPU after re-enable')
            results.append(result)
    finally:
        (directory/'ENABLED').unlink(missing_ok=True)
        try:provider.patch('/api/nodes/'+config['node_id'],json={'sharing':False})
        finally:agent.quit.set();agent.stop_job('實機驗證結束');runner.join(10)
        target=ROOT/'docs'/('gpu-results-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        target.write_text(json.dumps({'hardware':hw,'tested_at':time.time(),'jobs':results},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Evidence:',target)
        provider.close();requester.close()

if __name__=='__main__':main()

