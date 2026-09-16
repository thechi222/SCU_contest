import argparse
import contextlib
import getpass
import json
import logging
import os
import signal
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from .hardware import gpu,telemetry,docker
from .prepare import prepare,verify_profiles
from .runtime import Runner,Cancelled,cleanup_owned

LOG=logging.getLogger('relay-agent')

def client(config,authenticated=True):
    url=urlsplit(config['server'])
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost')):
        raise ValueError('區域網路連線需使用 HTTPS 與受信任憑證')
    if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('中央服務網址只能包含協定、主機與連接埠')
    import ssl
    verify=ssl.create_default_context(cafile=config.get('ca')) if config.get('ca') else True
    return httpx.Client(base_url=config['server'],verify=verify,timeout=httpx.Timeout(5,connect=3),
                        headers={'Authorization':'Bearer '+config['token']} if authenticated else {},trust_env=False)

class Agent:
    def __init__(self,directory,config,profiles):
        self.directory,self.config,self.profiles=directory,config,profiles
        self.hw=gpu(config['gpu']);verify_profiles(profiles,self.hw)
        cleanup_owned(config['node_id'])
        self.runner=Runner(self.hw['gpu_uuid'],profiles,config['node_id'])
        self.quit=threading.Event();self.cancelled=threading.Event()
        self.lock=threading.RLock();self.assignment=None;self.worker=None
        self.stage='載入模型';self.deadline=0;self.reason='';self.last_error=''
        self.enabled_file=directory/'ENABLED'
        self.capabilities={k:{n:p[n] for n in ('profile','cuda_verified','peak_vram_mb')} for k,p in profiles.items()}

    def stop_job(self,reason):
        self.reason=reason;self.cancelled.set()
        try:self.runner.stop()
        except Exception as e:LOG.error('停止容器失敗，持續重試：%s',e)

    def watchdog(self):
        while not self.quit.wait(.25):
            enabled=self.enabled_file.is_file()
            if self.assignment and (not enabled or time.monotonic()>=self.deadline):
                self.stop_job('本機停止或續約逾時')

    def set_stage(self,value):
        if value in ('下載輸入','載入模型','GPU 運算中','上傳結果'):self.stage=value

    def execute(self,assignment):
        attempt=assignment['attempt_id'];folder=self.directory/'jobs'/attempt
        folder.mkdir(parents=True,exist_ok=True)
        try:
            with client(self.config) as connection:
                self.set_stage('下載輸入')
                with connection.stream('GET',assignment['input_url']) as response:
                    response.raise_for_status();size=0
                    with (folder/'source').open('wb') as output:
                        for data in response.iter_bytes(1024*1024):
                            if self.cancelled.is_set():raise Cancelled()
                            size+=len(data)
                            if size>50*1024*1024:raise RuntimeError('輸入檔案過大')
                            output.write(data)
                    if size!=assignment['input_bytes']:raise RuntimeError('輸入傳輸未完整')
                if self.cancelled.is_set():raise Cancelled()
                self.set_stage('載入模型')
                metrics=self.runner.execute(assignment['kind'],folder,self.cancelled,self.set_stage)
                if self.cancelled.is_set():raise Cancelled()
                self.set_stage('上傳結果')
                names=['transcript.txt','subtitles.srt'] if assignment['kind']=='asr' else ['upscaled.png']
                with contextlib.ExitStack() as stack:
                    files=[('files',(name,stack.enter_context((folder/'output'/name).open('rb')),'application/octet-stream')) for name in names]
                    response=connection.post(f'/api/agent/attempts/{attempt}/complete',files=files,data={'metrics':json.dumps(metrics)},timeout=120)
                    response.raise_for_status()
                LOG.info('工作 %s 已完成',attempt[:8])
        except Cancelled:LOG.info('工作 %s 已停止：%s',attempt[:8],self.reason)
        except Exception as e:
            self.last_error=str(e)[:350];LOG.error('工作失敗：%s',self.last_error)
            try:
                with client(self.config) as connection:
                    connection.post(f'/api/agent/attempts/{attempt}/fail',json={'reason':self.last_error})
            except httpx.HTTPError:pass
        finally:
            # Local job data is removed only inside this agent's own resolved job folder.
            # Keep error logs and CUDA measurements; remove user input/results after upload or cancellation.
            for path in [folder/'source',*(folder/'output').glob('*')]:
                if path.is_file() and not path.is_symlink() and path.name not in ('metrics.json',):
                    path.unlink(missing_ok=True)

    def run(self):
        watcher=threading.Thread(target=self.watchdog,daemon=True);watcher.start()
        LOG.info('本機控制：relay-agent enable / relay-agent stop；Ctrl+C 結束')
        try:
            with client(self.config) as connection:
                while not self.quit.is_set():
                    started=time.monotonic()
                    if self.worker and not self.worker.is_alive():
                        self.worker=None;self.assignment=None
                    enabled=self.enabled_file.is_file()
                    try:
                        response=connection.post('/api/agent/heartbeat',json={'attempt_id':self.assignment['attempt_id'] if self.assignment else None,
                            'local_enabled':enabled,'capabilities':self.capabilities,'environment':{**self.hw,'services':{k:p['image_id'] for k,p in self.profiles.items()}},
                            'telemetry':telemetry(self.config['gpu']),'stage':self.stage if self.assignment else None})
                        response.raise_for_status();result=response.json()
                        if result['stop']:self.stop_job('中央服務已收回工作')
                        elif self.assignment:self.deadline=started+result['lease_seconds']-2
                        if not self.worker and enabled and result['sharing'] and result['within_schedule']:
                            claim=connection.post('/api/agent/claim');claim.raise_for_status()
                            assignment=claim.json()['assignment']
                            if assignment:
                                self.cancelled=threading.Event();self.deadline=started+assignment['lease_seconds']-2
                                self.assignment=assignment;self.reason='';self.stage='下載輸入'
                                self.worker=threading.Thread(target=self.execute,args=(assignment,),daemon=True);self.worker.start()
                        self.last_error=''
                    except (httpx.HTTPError,ValueError) as e:
                        self.last_error=str(e)[:300]
                        # A failed renewal immediately releases GPU; central lease expiry performs the retry.
                        if self.assignment:self.stop_job('中央服務無法續約')
                        LOG.warning('中央服務暫時無法連線：%s',self.last_error)
                    status={'node_id':self.config['node_id'],'local_enabled':enabled,'attempt_id':self.assignment['attempt_id'] if self.assignment else None,
                            'stage':self.stage if self.assignment else '等待接單','last_error':self.last_error,'updated_at':time.time()}
                    (self.directory/'status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
                    self.quit.wait(max(0,5-(time.monotonic()-started)))
        finally:
            self.quit.set();self.stop_job('程式結束')
            if self.worker:self.worker.join(8)

def main():
    parser=argparse.ArgumentParser(description='算力接力站 GPU 接力程式')
    parser.add_argument('--dir',type=Path,default=Path('.agent'))
    sub=parser.add_subparsers(dest='command',required=True)
    doctor=sub.add_parser('doctor');doctor.add_argument('--gpu',type=int,default=0)
    prep=sub.add_parser('prepare');prep.add_argument('--gpu',type=int,default=0);prep.add_argument('--kind',choices=['asr','upscale','all'],default='all');prep.add_argument('--skip-build',action='store_true')
    pair=sub.add_parser('pair');pair.add_argument('--server',required=True);pair.add_argument('--ca');pair.add_argument('--name',required=True);pair.add_argument('--gpu',type=int,default=0)
    for command in ('run','enable','stop','status'):sub.add_parser(command)
    args=parser.parse_args();directory=args.dir.resolve();directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    config_file=directory/'config.json'
    if args.command=='doctor':
        print(json.dumps({'hardware':gpu(args.gpu),'telemetry':telemetry(args.gpu),'docker':docker(['info','--format','{{.ServerVersion}}']).stdout.strip()},ensure_ascii=False,indent=2));return
    if args.command=='prepare':prepare(directory,args.gpu,['asr','upscale'] if args.kind=='all' else [args.kind],not args.skip_build);return
    if args.command=='enable':(directory/'ENABLED').touch();print('本機已允許接單；仍需在平台開啟分享。');return
    if args.command=='stop':
        (directory/'ENABLED').unlink(missing_ok=True)
        if config_file.exists():cleanup_owned(json.loads(config_file.read_text('utf-8'))['node_id'])
        print('本機已停止接單，並移除自己的工作容器。');return
    if args.command=='status':print((directory/'status.json').read_text('utf-8') if (directory/'status.json').exists() else '接力程式尚未啟動');return
    profiles_file=directory/'profiles.json'
    profiles=json.loads(profiles_file.read_text('utf-8')) if profiles_file.exists() else {}
    if args.command=='pair':
        if config_file.exists():parser.error('設備已配對，請使用既有設定；重新配對需管理者撤銷舊設備並使用另一個 --dir')
        hw=gpu(args.gpu);verify_profiles(profiles,hw)
        config={'server':args.server.rstrip('/'),'ca':str(Path(args.ca).resolve()) if args.ca else None,'gpu':args.gpu}
        code=getpass.getpass('一次性配對碼：')
        with client(config,False) as connection:
            response=connection.post('/api/agent/pair',json={'code':code,'name':args.name,**{k:hw[k] for k in ('gpu_uuid','gpu_name','memory_mb')},
                'capabilities':{k:{n:p[n] for n in ('profile','cuda_verified','peak_vram_mb')} for k,p in profiles.items()},'environment':hw})
            response.raise_for_status();config.update(response.json())
        config_file.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');config_file.chmod(0o600)
        print('配對完成。執行 run 後，可使用 enable 與平台 ON 開始分享。');return
    config=json.loads(config_file.read_text('utf-8'))
    # OS file lock prevents two local processes from heartbeating the same node.
    with (directory/'run.lock').open('a+b') as lock:
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt;msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl;fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:parser.error('同一設備的接力程式已在執行')
        agent=Agent(directory,config,profiles)
        signal.signal(signal.SIGINT,lambda *_:agent.quit.set())
        signal.signal(signal.SIGTERM,lambda *_:agent.quit.set())
        agent.run()

if __name__=='__main__':main()
