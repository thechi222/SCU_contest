"""Run genuine CUDA jobs in the disposable UI QA server, never seed fake results."""
import json
import tempfile
import threading
import time
from pathlib import Path
import httpx
from agent.hardware import gpu
from agent.main import Agent

root=Path(__file__).resolve().parent.parent
profiles=json.loads((root/'.agent/profiles.json').read_text('utf-8'))
with httpx.Client(base_url='http://127.0.0.1:8766',headers={'X-Relay-Request':'1'},timeout=120,trust_env=False) as c:
    c.post('/api/auth/login',json={'username':'uiqa','password':'local-ui-check-only'}).raise_for_status()
    code=c.post('/api/pairing-codes').json()['code'];hw=gpu(0)
    r=c.post('/api/agent/pair',json={'code':code,'name':'實機介面驗證 RTX 3050',**{k:hw[k] for k in ('gpu_uuid','gpu_name','memory_mb')},'environment':hw,
        'capabilities':{k:{n:p[n] for n in ('profile','cuda_verified','peak_vram_mb')} for k,p in profiles.items()}})
    r.raise_for_status();config={**r.json(),'server':'http://127.0.0.1:8766','ca':None,'gpu':0}
    with tempfile.TemporaryDirectory(prefix='relay-gpu-ui-') as temp:
        directory=Path(temp);(directory/'ENABLED').touch()
        agent=Agent(directory,config,profiles)
        c.patch('/api/nodes/'+config['node_id'],json={'sharing':True}).raise_for_status()
        runner=threading.Thread(target=agent.run,daemon=True);runner.start()
        try:
            ids=[]
            for kind,name in [('asr','introduction.wav'),('upscale','calibration.png')]:
                with (root/'demo-assets'/name).open('rb') as f:
                    r=c.post('/api/batches',data={'kind':kind,'name':'真實 GPU 成果預覽驗證','is_demo':'true'},files={'files':(name,f)})
                r.raise_for_status();ids+=r.json()['job_ids']
            for _ in range(300):
                jobs=[j for j in c.get('/api/state').json()['jobs'] if j['id'] in ids]
                if any(j['status']=='failed' for j in jobs):raise RuntimeError('GPU result preview fixture failed')
                if all(j['status']=='completed' for j in jobs):
                    print('Two real GPU results available in temporary UI QA server.');break
                time.sleep(1)
            else:raise TimeoutError('GPU QA timed out')
        finally:
            c.patch('/api/nodes/'+config['node_id'],json={'sharing':False})
            agent.quit.set();agent.stop_job('介面 GPU 驗證結束');runner.join(10)
