"""Measure upload, queue, processing and downloads using actual platform jobs."""
import argparse
import contextlib
import getpass
import hashlib
import json
import ssl
import time
from pathlib import Path
import httpx

parser=argparse.ArgumentParser();parser.add_argument('--server',default='http://127.0.0.1:8765');parser.add_argument('--user',required=True);parser.add_argument('--ca');parser.add_argument('--kind',choices=['asr','upscale'],required=True);parser.add_argument('--label',required=True);parser.add_argument('--output',type=Path,default=Path('data/benchmarks'));parser.add_argument('files',nargs='+',type=Path)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
verify=ssl.create_default_context(cafile=args.ca) if args.ca else True
with httpx.Client(base_url=args.server,verify=verify,headers={'X-Relay-Request':'1'},timeout=150,trust_env=False) as c:
    r=c.post('/api/auth/login',json={'username':args.user,'password':getpass.getpass('密碼：')});r.raise_for_status()
    state=c.get('/api/state').json()
    inputs=[{'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in args.files]
    start=time.perf_counter()
    with contextlib.ExitStack() as stack:
        files=[('files',(p.name,stack.enter_context(p.open('rb')))) for p in args.files]
        r=c.post('/api/batches',data={'kind':args.kind,'name':args.label,'is_demo':'true'},files=files);r.raise_for_status();batch=r.json()
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        r=c.get('/api/state');r.raise_for_status()
        jobs=[j for j in r.json()['jobs'] if j['batch_id']==batch['batch_id']]
        done=sum(j['status']=='completed' for j in jobs)
        print(f'{done}/{len(args.files)} completed',flush=True)
        if len(jobs)==len(args.files) and all(j['status'] in ('completed','failed','cancelled') for j in jobs):break
        time.sleep(2)
    else:raise TimeoutError('測量超過一小時，請在工作頁查看或取消')
    if done:
        r=c.get('/api/batches/'+batch['batch_id']+'/download');r.raise_for_status()
        (args.output/(batch['batch_id']+'.zip')).write_bytes(r.content)
    result={'label':args.label,'batch_id':batch['batch_id'],'input_count':len(inputs),'inputs':inputs,'elapsed_including_upload_download_seconds':time.perf_counter()-start,'max_running':state['user']['max_running'],'ready_node_ids':[n['id'] for n in state['nodes'] if n['online'] and n['sharing']],'jobs':jobs}
    target=args.output/(batch['batch_id']+'.json');target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Measured result: '+str(target))
