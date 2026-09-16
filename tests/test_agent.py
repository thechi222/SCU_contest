import json
import threading
import time
from types import SimpleNamespace
import pytest
from agent.main import client,Agent
from agent.runtime import Runner,Cancelled,cleanup_owned

def test_lan_requires_tls():
    with pytest.raises(ValueError):client({'server':'http://192.168.1.10:8765','token':'test'})
    with client({'server':'http://127.0.0.1:8765','token':'test'}) as c:
        assert c.headers['Authorization']=='Bearer test'

def test_local_watchdog_stops_without_server(tmp_path):
    agent=Agent.__new__(Agent)
    agent.quit=threading.Event();agent.cancelled=threading.Event();agent.assignment={'id':'test'}
    agent.enabled_file=tmp_path/'ENABLED';agent.enabled_file.touch()
    agent.deadline=time.monotonic()+20;called=[]
    agent.runner=SimpleNamespace(stop=lambda:called.append(time.monotonic()))
    worker=threading.Thread(target=agent.watchdog);worker.start()
    agent.enabled_file.unlink();start=time.monotonic()
    assert agent.cancelled.wait(1)
    agent.quit.set();worker.join(1)
    assert called and called[0]-start<1

def test_watchdog_lease_timeout(tmp_path):
    agent=Agent.__new__(Agent);agent.quit=threading.Event();agent.cancelled=threading.Event()
    agent.assignment={'id':'test'};agent.enabled_file=tmp_path/'ENABLED';agent.enabled_file.touch()
    agent.deadline=time.monotonic()-1;agent.runner=SimpleNamespace(stop=lambda:None)
    worker=threading.Thread(target=agent.watchdog);worker.start()
    assert agent.cancelled.wait(1)
    agent.quit.set();worker.join(1)

def test_cleanup_only_owned_containers(monkeypatch):
    calls=[];name='relay-'+'b'*32;owner='a'*32
    def command(args,**kwargs):
        calls.append(args);return SimpleNamespace(stdout=name+'\n' if args[0]=='ps' else '')
    monkeypatch.setattr('agent.runtime.docker',command)
    cleanup_owned(owner)
    assert calls==[['ps','-a','--filter','label=relay-owner='+owner,'--format','{{.Names}}'],['rm','-f',name]]

def test_runner_rejects_mutable_image_and_cancel(tmp_path):
    runner=Runner('GPU-test',{'asr':{'image_id':'some:latest'}})
    with pytest.raises(ValueError):runner.execute('asr',tmp_path,threading.Event())

def test_worker_container_security_flags(tmp_path,monkeypatch):
    folder=tmp_path/('a'*32);folder.mkdir();(folder/'source').write_bytes(b'test')
    output=folder/'output';output.mkdir()
    (output/'metrics.json').write_text(json.dumps({'cuda_verified':True,'profile':'test-profile','gpu_seconds':1}))
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps({'Running':False,'ExitCode':0}) if args[0]=='inspect' else '',stderr='')
    monkeypatch.setattr('agent.runtime.docker',command)
    runner=Runner('GPU-test',{'asr':{'image_id':'sha256:'+'b'*64,'profile':'test-profile','models':str(tmp_path),'manifest_sha256':'x'}},'c'*32)
    result=runner.execute('asr',folder,threading.Event())
    create=calls[0]
    assert create[create.index('--network')+1]=='none'
    assert '--read-only' in create and 'ALL' in create and 'no-new-privileges' in create
    assert 'relay-owner='+'c'*32 in create
    assert any('/input/source,readonly' in part for part in create)
    assert any('/models,readonly' in part for part in create)
    assert result['cuda_verified'] is True
