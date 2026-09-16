"""Real TCP outage for one GPU agent through an owned loopback proxy.

Does not disable the user's network or stop the central server.
"""
import json
import logging
import re
import select
import socket
import socketserver
import threading
import time
from pathlib import Path
import httpx
from PIL import Image
from agent.main import Agent
from agent.hardware import telemetry,docker

root=Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
online=threading.Event();online.set()

class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        if not online.is_set():return
        with socket.create_connection(('127.0.0.1',8765),timeout=3) as upstream:
            while online.is_set():
                ready,_,_=select.select([self.request,upstream],[],[],.1)
                for source in ready:
                    data=source.recv(65536)
                    if not data:return
                    (upstream if source is self.request else self.request).sendall(data)

class Proxy(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=True
    def handle_error(self,request,client_address):pass  # expected during intentional disconnect

profiles=json.loads((root/'.agent/profiles.json').read_text('utf-8'))
config=json.loads((root/'.agent/config.json').read_text('utf-8'))
credentials=(root/'data/initial-accounts.md').read_text('utf-8')
password=re.search(r'\| provider \|[^\n]+`([^`]+)`',credentials).group(1)
with Proxy(('127.0.0.1',0),Forward) as proxy,httpx.Client(base_url='http://127.0.0.1:8765',headers={'X-Relay-Request':'1'},timeout=120,trust_env=False) as c:
    c.post('/api/auth/login',json={'username':'provider','password':password}).raise_for_status()
    server=threading.Thread(target=proxy.serve_forever,daemon=True);server.start()
    isolated_config={**config,'server':'http://127.0.0.1:'+str(proxy.server_address[1])}
    agent=Agent(root/'.agent',isolated_config,profiles)
    (root/'.agent/ENABLED').touch()
    c.patch('/api/nodes/'+config['node_id'],json={'sharing':True}).raise_for_status()
    runner=threading.Thread(target=agent.run,daemon=True);runner.start()
    evidence={'scope':'one real GPU agent, actual TCP connections cut by local test proxy; recovery on same physical GPU','started_at':time.time()}
    try:
        path=root/'data/network-test.png'
        with Image.open(root/'demo-assets/calibration.png') as source:source.resize((2048,1536)).save(path)
        baseline=telemetry(0).get('memory_used_mb')
        with path.open('rb') as f:
            r=c.post('/api/batches',data={'kind':'upscale','name':'實機 TCP 斷線與恢復驗證','is_demo':'true'},files={'files':('network-test.png',f)})
        r.raise_for_status();job_id=r.json()['job_ids'][0]
        def state():
            r=c.get('/api/state');r.raise_for_status();data=r.json()
            return next(j for j in data['jobs'] if j['id']==job_id),next(n for n in data['nodes'] if n['id']==config['node_id'])
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            job,node=state()
            if job['stage']=='GPU 運算中':break
            if job['status'] in ('completed','failed'):raise RuntimeError('未捕捉到運算階段')
            time.sleep(.5)
        else:raise TimeoutError('未進入運算')
        cut=time.perf_counter();online.clear();print('Disconnected real agent TCP transport.',flush=True)
        released=None;requeued=None;deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            job,node=state();elapsed=time.perf_counter()-cut
            if released is None:
                running=docker(['ps','--filter','label=relay-owner='+config['node_id'],'--format','{{.Names}}']).stdout.strip()
                used=telemetry(0).get('memory_used_mb')
                if not running and used is not None and baseline is not None and used<=baseline+128:released=elapsed
            if job['status']=='retrying' and not node['online']:
                requeued=elapsed;break
            time.sleep(.5)
        evidence.update(gpu_release_seconds=released,offline_and_retry_seconds=requeued)
        if requeued is None or released is None:raise RuntimeError('未在 35 秒內確認釋放與重排')
        print('GPU release:',round(released,2),'seconds; offline + retry:',round(requeued,2),'seconds',flush=True)
        online.set();deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            job,node=state()
            if job['status']=='completed':
                evidence['job']=job
                out=root/'data/verified-results'/job_id;out.mkdir(parents=True,exist_ok=True)
                for artifact in job['artifacts']:
                    r=c.get('/api/artifacts/'+artifact['id']);r.raise_for_status();(out/artifact['name']).write_bytes(r.content)
                print('Real GPU retry completed after reconnection.',flush=True);break
            if job['status']=='failed':raise RuntimeError(job['error'])
            time.sleep(1)
        else:raise TimeoutError('重試逾時')
    except Exception as error:
        evidence['error']=str(error)
        if 'job_id' in locals():evidence['job']=state()[0]
        raise
    finally:
        online.set();(root/'.agent/ENABLED').unlink(missing_ok=True)
        c.patch('/api/nodes/'+config['node_id'],json={'sharing':False})
        agent.quit.set();agent.stop_job('TCP 斷線驗證結束');runner.join(10);proxy.shutdown()
        evidence['finished_at']=time.time()
        target=root/'docs'/('network-results-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
        target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Evidence:',target)
