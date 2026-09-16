"""Protocol fixtures simulate agents, NOT real GPU computation."""
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from PIL import Image
from relay.app import create_app
from relay.config import Settings,PROFILES
from relay.store import Store
from relay.models import Heartbeat

PASS='test-only-password-349!'
CAPS={kind:{'profile':profile,'cuda_verified':True,'peak_vram_mb':1000} for kind,profile in PROFILES.items()}

def png(size=(32,24)):
    b=io.BytesIO();Image.new('RGB',size,'#65b588').save(b,format='PNG');return b.getvalue()

@pytest.fixture
def env(tmp_path):
    now=[1_800_000_000.0]
    settings=Settings(data_dir=tmp_path,frontend_dir=tmp_path/'no-ui')
    store=Store(settings,clock=lambda:now[0])
    for name,role in [('admin','admin'),('alice','member'),('bob','member'),('provider','member')]:
        store.create_user(name,PASS,name,role)
    app=create_app(settings,store=store)
    clients={}
    for name in ('admin','alice','bob','provider'):
        c=TestClient(app,headers={'X-Relay-Request':'1'})
        assert c.post('/api/auth/login',json={'username':name,'password':PASS}).status_code==200
        clients[name]=c
    yield {'store':store,'app':app,'now':now,**clients}
    for c in clients.values():c.close()

def submit(c,count=1,kind='upscale',demo=False,name='sample.png'):
    r=c.post('/api/batches',data={'kind':kind,'name':'test batch','is_demo':str(demo).lower()},
             files=[('files',(name if kind=='upscale' else 'sample.wav',png() if kind=='upscale' else b'RIFF-test-protocol-input')) for _ in range(count)])
    assert r.status_code==200,r.text
    return r.json()

def node(env,number=1,caps=None):
    code=env['provider'].post('/api/pairing-codes').json()['code']
    c=TestClient(env['app'])
    r=c.post('/api/agent/pair',json={'code':code,'name':'Fixture GPU '+str(number),'gpu_uuid':'GPU-fixture-'+str(number),'gpu_name':'TEST PROTOCOL ONLY','memory_mb':4096,'capabilities':caps or CAPS})
    assert r.status_code==200,r.text
    data=r.json();c.headers['Authorization']='Bearer '+data['token']
    assert env['provider'].patch('/api/nodes/'+data['node_id'],json={'sharing':True}).status_code==200
    heartbeat(c,caps=caps)
    return c,data['node_id']

def heartbeat(c,attempt=None,enabled=True,caps=None):
    return c.post('/api/agent/heartbeat',json={'attempt_id':attempt,'local_enabled':enabled,'capabilities':caps or CAPS,'telemetry':{'memory_free_mb':4000},'stage':'GPU 運算中' if attempt else None})

def claim(c):
    r=c.post('/api/agent/claim');assert r.status_code==200,r.text;return r.json()['assignment']

def finish(c,a,gpu=True,profile=None,duplicates=False,size=(64,48)):
    files=[('files',('upscaled.png',png(size),'image/png'))] if a['kind']=='upscale' else [('files',('transcript.txt','測試逐字稿'.encode())),('files',('subtitles.srt',b'1\n00:00:00,000 --> 00:00:01,000\ntest\n'))]
    if duplicates:files+=files[:1]
    return c.post('/api/agent/attempts/'+a['attempt_id']+'/complete',data={'metrics':json.dumps({'profile':profile or a['profile'],'cuda_verified':gpu,'gpu_seconds':2.5,'engine':'TEST FIXTURE'})},files=files)

def jobs(c):return c.get('/api/state').json()['jobs']

def test_permissions_and_csrf(env):
    batch=submit(env['alice']);job=batch['job_ids'][0]
    assert env['bob'].get('/api/jobs/'+job+'/input').status_code==404
    assert env['bob'].post('/api/jobs/'+job+'/cancel').status_code==404
    assert env['bob'].get('/api/admin/report').status_code==403
    assert env['bob'].post('/api/admin/users',json={}).status_code==403
    n,nid=node(env)
    assert env['alice'].patch('/api/nodes/'+nid,json={'sharing':False}).status_code==404
    stranger=TestClient(env['app'])
    assert stranger.post('/api/auth/login',json={'username':'alice','password':PASS}).status_code==403
    assert env['alice'].post('/api/auth/logout',headers={'Origin':'https://evil.example'}).status_code==403
    assert 'token_hash' not in json.dumps(env['alice'].get('/api/state').json())
    assert 'environment' not in env['alice'].get('/api/state').json()['nodes'][0]

def test_round_robin_fifo_user_limit_and_three_nodes(env):
    first=submit(env['alice'],3)['job_ids'];second=submit(env['bob'],2)['job_ids']
    n1,_=node(env,1);n2,_=node(env,2);n3,_=node(env,3);n4,_=node(env,4)
    a1=claim(n1);a2=claim(n2);a3=claim(n3);a4=claim(n4)
    assert [a1['job_id'],a2['job_id'],a3['job_id'],a4['job_id']]==[first[0],second[0],first[1],second[1]]
    assert claim(n1) is None
    n5,_=node(env,5);assert claim(n5) is None  # alice's 2 active jobs exhaust quota
    assert finish(n1,a1).status_code==200
    assert claim(n5)['job_id']==first[2]

def test_concurrent_claim_only_once(env):
    submit(env['alice']);_,nid=node(env)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:env['store'].claim(nid),range(4)))
    assert sum(r is not None for r in results)==1

def test_off_requeues_and_fences_old_attempt(env):
    submit(env['alice']);n1,id1=node(env,1);n2,_=node(env,2)
    first=claim(n1)
    env['provider'].patch('/api/nodes/'+id1,json={'sharing':False})
    assert jobs(env['alice'])[0]['status']=='retrying'
    second=claim(n2)
    assert first['attempt_id']!=second['attempt_id']
    assert finish(n1,first).status_code==409
    assert heartbeat(n1,first['attempt_id']).json()['stop'] is True
    assert finish(n2,second).status_code==200
    assert len(jobs(env['alice'])[0]['artifacts'])==1

def test_disconnect_retry_limit_and_restart(env):
    submit(env['alice']);n,_=node(env)
    a=claim(n);env['now'][0]+=21
    restarted=Store(env['store'].settings,clock=lambda:env['now'][0]);restarted.reap_expired()
    assert jobs(env['alice'])[0]['status']=='retrying'
    assert finish(n,a).status_code==409
    heartbeat(n)
    for _ in range(2):
        a=claim(n);assert a
        assert n.post('/api/agent/attempts/'+a['attempt_id']+'/fail',json={'reason':'fixture failure'}).status_code==200
    assert jobs(env['alice'])[0]['status']=='failed'
    assert jobs(env['alice'])[0]['attempt_count']==3
    assert claim(n) is None

def test_cancel_never_retries(env):
    job=submit(env['alice'])['job_ids'][0];n,_=node(env);a=claim(n)
    env['alice'].post('/api/jobs/'+job+'/cancel')
    assert heartbeat(n,a['attempt_id']).json()['stop']
    assert finish(n,a).status_code==409
    env['now'][0]+=25;heartbeat(n)
    assert claim(n) is None
    assert jobs(env['alice'])[0]['status']=='cancelled'

def test_gpu_evidence_and_result_validation(env):
    submit(env['alice']);n,_=node(env);a=claim(n)
    assert finish(n,a,gpu=False).status_code==422
    assert finish(n,a,profile='different-model').status_code==422
    assert finish(n,a,duplicates=True).status_code==422
    assert finish(n,a,size=(65,48)).status_code==422
    assert finish(n,a).status_code==200
    assert finish(n,a).status_code==409
    job=jobs(env['alice'])[0]
    assert job['attempts'][0]['gpu_verified']==1
    artifact=job['artifacts'][0]['id']
    assert env['alice'].get('/api/artifacts/'+artifact).status_code==200
    assert env['bob'].get('/api/artifacts/'+artifact).status_code==404

def test_audio_result_batch_archive(env):
    batch=submit(env['alice'],2,'asr');n,_=node(env)
    a=claim(n);assert finish(n,a).status_code==200
    a=claim(n);assert finish(n,a).status_code==200
    response=env['alice'].get('/api/batches/'+batch['batch_id']+'/download')
    assert response.status_code==200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(archive.namelist())==4
    assert env['bob'].get('/api/batches/'+batch['batch_id']+'/download').status_code==404

def test_pairing_one_time_and_revocation(env):
    code=env['provider'].post('/api/pairing-codes').json()['code']
    body={'code':code,'name':'test','gpu_uuid':'GPU-once','gpu_name':'TEST','memory_mb':4000}
    c=TestClient(env['app']);r=c.post('/api/agent/pair',json=body);assert r.status_code==200
    assert c.post('/api/agent/pair',json={**body,'gpu_uuid':'GPU-other'}).status_code==400
    nid=r.json()['node_id'];c.headers['Authorization']='Bearer '+r.json()['token']
    assert env['provider'].patch('/api/nodes/'+nid,json={'revoked':True}).status_code==403
    env['admin'].patch('/api/nodes/'+nid,json={'revoked':True})
    assert heartbeat(c).status_code==401

def test_schedules_and_local_stop(env):
    submit(env['alice']);n,nid=node(env);a=claim(n)
    assert heartbeat(n,a['attempt_id'],enabled=False).json()['stop']
    assert claim(n) is None
    assert env['provider'].patch('/api/nodes/'+nid,json={'schedule_start':'23:00'}).status_code==422
    store=env['store']
    env['now'][0]=1_800_057_600.0  # use explicit UTC hour below
    from datetime import datetime,timezone
    def hour(h):env['now'][0]=datetime(2027,1,1,h,tzinfo=timezone.utc).timestamp()
    schedule={'schedule_start':'22:00','schedule_end':'06:00','utc_offset_minutes':0}
    hour(23);assert store.in_schedule(schedule)
    hour(5);assert store.in_schedule(schedule)
    hour(6);assert not store.in_schedule(schedule)
    hour(12);assert not store.in_schedule(schedule)

def test_admin_reset_only_selected_demo_and_restore(env):
    normal=submit(env['alice']);demo=submit(env['alice'],demo=True);other=submit(env['alice'],demo=True)
    assert env['admin'].post('/api/admin/demo/reset',json={'batch_ids':[demo['batch_id'],normal['batch_id']],'confirmation':'RESET DEMO'}).status_code==400
    assert len(jobs(env['alice']))==3
    assert env['admin'].post('/api/admin/demo/reset',json={'batch_ids':[demo['batch_id']],'confirmation':'RESET DEMO'}).status_code==200
    assert {j['batch_id'] for j in jobs(env['alice'])}=={normal['batch_id'],other['batch_id']}
    assert env['alice'].get('/api/jobs/'+demo['job_ids'][0]+'/input').status_code==200
    env['admin'].post('/api/admin/demo/restore')
    assert len(jobs(env['alice']))==3

def test_quota_validation_disable_and_csv(env):
    u=env['alice'].get('/api/state').json()['user']['id']
    assert env['admin'].patch('/api/admin/users/'+u,json={'daily_limit':1}).status_code==200
    submit(env['alice'],name='=formula.png')
    r=env['alice'].post('/api/batches',data={'kind':'upscale'},files={'files':('x.png',png())})
    assert r.status_code==429
    assert "'=formula.png" in env['admin'].get('/api/admin/report').text
    bad=env['bob'].post('/api/batches',data={'kind':'upscale'},files={'files':('x.png',b'not image')})
    assert bad.status_code==422
    big=env['bob'].post('/api/batches',data={'kind':'upscale'},files={'files':('x.png',png((2049,2)))})
    assert big.status_code==422
    env['admin'].patch('/api/admin/users/'+u,json={'enabled':False})
    assert env['alice'].get('/api/state').status_code==401
    assert next(j for j in jobs(env['admin']) if j['user_id']==u)['status']=='cancelled'

def test_capability_matching_memory_and_lease_renewal(env):
    submit(env['alice'],kind='asr')
    n,_=node(env,caps={'upscale':CAPS['upscale']})
    assert claim(n) is None
    heartbeat(n)
    n.post('/api/agent/heartbeat',json={'local_enabled':True,'capabilities':CAPS,'telemetry':{'memory_free_mb':20}})
    assert claim(n) is None
    heartbeat(n);a=claim(n)
    env['now'][0]+=15;assert heartbeat(n,a['attempt_id']).status_code==200
    env['now'][0]+=10;assert finish(n,a).status_code==200

def test_password_change_invalidates_sessions(env):
    r=env['alice'].post('/api/auth/password',json={'current_password':PASS,'new_password':'another-test-password!'});assert r.status_code==200
    assert env['alice'].get('/api/state').status_code==401
    assert env['alice'].post('/api/auth/login',json={'username':'alice','password':PASS}).status_code==401

def test_login_throttling(env):
    for _ in range(10):
        assert env['bob'].post('/api/auth/login',json={'username':'nobody','password':'incorrect'}).status_code==401
    assert env['bob'].post('/api/auth/login',json={'username':'nobody','password':'incorrect'}).status_code==429
