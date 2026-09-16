from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sqlite3
import threading
import time
import uuid
from fastapi import HTTPException
from .config import Settings, PROFILES, ACTIVE, PENDING
from .security import hash_password, token_hash, new_token

def uid() -> str:
    return uuid.uuid4().hex

def unpack(row):
    return dict(row) if row is not None else None

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class Store:
    def __init__(self, settings: Settings, clock=time.time):
        self.settings, self.clock = settings, clock
        self.lock = threading.RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        (settings.data_dir / 'files').mkdir(exist_ok=True)
        self.path = settings.data_dir / 'relay.sqlite3'
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))

    def connect(self):
        c = sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    @contextmanager
    def transaction(self):
        with self.lock:
            c = self.connect()
            try:
                c.execute('BEGIN IMMEDIATE')
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise
            finally:
                c.close()

    def event(self, c, kind, message, *, user_id=None, node_owner_id=None, job_id=None, node_id=None):
        c.execute('INSERT INTO events(user_id,node_owner_id,job_id,node_id,kind,message,created_at) VALUES(?,?,?,?,?,?,?)',
                  (user_id,node_owner_id,job_id,node_id,kind,message,self.clock()))

    def create_user(self, username, password, display_name, role='member', max_running=2, daily_limit=100):
        if len(password) < 12:
            raise ValueError('密碼至少 12 個字元')
        user_id = uid()
        with self.transaction() as c:
            c.execute('INSERT INTO users(id,username,display_name,password_hash,role,max_running,daily_limit,created_at) VALUES(?,?,?,?,?,?,?,?)',
                      (user_id,username,display_name,hash_password(password),role,max_running,daily_limit,self.clock()))
        return user_id

    def user_by_session(self, token):
        with self.connect() as c:
            row = c.execute('SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>? AND u.enabled=1',
                            (token_hash(token or ''),self.clock())).fetchone()
        if not row:
            raise HTTPException(401, '請先登入，或重新登入已到期的工作階段')
        return unpack(row)

    def node_by_token(self, token):
        with self.connect() as c:
            row = c.execute('SELECT n.* FROM nodes n JOIN users u ON n.owner_id=u.id WHERE n.token_hash=? AND n.revoked=0 AND u.enabled=1',
                            (token_hash(token),)).fetchone()
        if not row:
            raise HTTPException(401, '設備憑證無效或已撤銷')
        return unpack(row)

    @staticmethod
    def public_user(row):
        return {k: row[k] for k in ('id','username','display_name','role','enabled','max_running','daily_limit')}

    def in_schedule(self, node):
        start, end = node['schedule_start'], node['schedule_end']
        if not start or not end or start == end:
            return True
        local = datetime.fromtimestamp(self.clock(), timezone(timedelta(minutes=node['utc_offset_minutes'])))
        now = local.strftime('%H:%M')
        return start <= now < end if start < end else now >= start or now < end

    def eligible(self, node):
        return (not node['revoked'] and node['sharing'] and node['local_enabled']
                and self.clock() - node['last_seen'] < self.settings.lease_seconds and self.in_schedule(node))

    def end_attempt(self, c, attempt, reason, *, retry=True):
        now = self.clock()
        c.execute('UPDATE attempts SET ended_at=?,outcome=?,error=? WHERE id=? AND ended_at IS NULL',
                  (now, 'interrupted' if retry else 'cancelled', reason, attempt['id']))
        job = c.execute('SELECT * FROM jobs WHERE id=?', (attempt['job_id'],)).fetchone()
        if not job or job['active_attempt_id'] != attempt['id']:
            return
        status = 'retrying' if retry and job['attempt_count'] < 3 else ('failed' if retry else 'cancelled')
        stage = '等待其他設備重新執行' if status == 'retrying' else ('已取消' if status == 'cancelled' else '已達重試上限')
        c.execute('UPDATE jobs SET status=?,active_attempt_id=NULL,stage=?,progress=NULL,error=?,completed_at=? WHERE id=?',
                  (status,stage,reason,None if status == 'retrying' else now,job['id']))
        node = c.execute('SELECT owner_id FROM nodes WHERE id=?', (attempt['node_id'],)).fetchone()
        self.event(c,status,reason,user_id=job['user_id'],node_owner_id=node['owner_id'] if node else None,job_id=job['id'],node_id=attempt['node_id'])

    def reap(self, c):
        for attempt in c.execute('SELECT * FROM attempts WHERE ended_at IS NULL AND lease_until<=?', (self.clock(),)).fetchall():
            self.end_attempt(c, attempt, '設備未在期限內回報，工作已收回')
        for attempt in c.execute('SELECT a.* FROM attempts a JOIN nodes n ON a.node_id=n.id WHERE a.ended_at IS NULL').fetchall():
            node = c.execute('SELECT * FROM nodes WHERE id=?',(attempt['node_id'],)).fetchone()
            if not self.in_schedule(node):
                self.end_attempt(c,attempt,'已超出機主設定的分享時段')
        c.execute('DELETE FROM sessions WHERE expires_at<?',(self.clock(),))

    def reap_expired(self):
        with self.transaction() as c:
            self.reap(c)

    def issue_pairing_code(self, owner_id):
        code = new_token()[:16].upper()
        with self.transaction() as c:
            c.execute('INSERT INTO pairing_codes VALUES(?,?,?,NULL)',(token_hash(code),owner_id,self.clock()+600))
        return {'code':code,'expires_in':600}

    def pair(self, body):
        now, node_id, token = self.clock(), uid(), new_token()
        with self.transaction() as c:
            code = c.execute('SELECT p.* FROM pairing_codes p JOIN users u ON p.owner_id=u.id WHERE p.code_hash=? AND p.used_at IS NULL AND p.expires_at>? AND u.enabled=1',
                             (token_hash(body.code.strip().upper()),now)).fetchone()
            if not code:
                raise HTTPException(400,'配對碼已使用、已過期或不存在')
            existing = c.execute('SELECT * FROM nodes WHERE gpu_uuid=?',(body.gpu_uuid,)).fetchone()
            if existing:
                raise HTTPException(409,'這張 GPU 已加入平台，請使用原設備設定；若需重新配對，請管理者撤銷並移除舊設備')
            c.execute('INSERT INTO nodes(id,owner_id,name,token_hash,gpu_uuid,gpu_name,memory_mb,capabilities,environment,last_seen,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (node_id,code['owner_id'],body.name,token_hash(token),body.gpu_uuid,body.gpu_name,body.memory_mb,json.dumps(body.capabilities),json.dumps(body.environment),now,now))
            c.execute('UPDATE pairing_codes SET used_at=? WHERE code_hash=?',(now,code['code_hash']))
            self.event(c,'node_paired',f'{body.name} 已加入，等待機主開啟共享',node_owner_id=code['owner_id'],node_id=node_id)
        return {'node_id':node_id,'token':token,'heartbeat_seconds':self.settings.heartbeat_seconds,'lease_seconds':self.settings.lease_seconds}

    def heartbeat(self, node_id, body):
        now = self.clock()
        with self.transaction() as c:
            self.reap(c)
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            c.execute('UPDATE nodes SET last_seen=?,telemetry=?,local_enabled=?,capabilities=?,environment=? WHERE id=?',
                      (now,json.dumps(body.telemetry),int(body.local_enabled),json.dumps(body.capabilities),json.dumps(body.environment),node_id))
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            active = c.execute('SELECT * FROM attempts WHERE node_id=? AND ended_at IS NULL',(node_id,)).fetchone()
            stop = False
            if active:
                user_enabled = c.execute('SELECT enabled FROM users WHERE id=(SELECT user_id FROM jobs WHERE id=?)',(active['job_id'],)).fetchone()[0]
                if not self.eligible(node) or not user_enabled or body.attempt_id != active['id']:
                    self.end_attempt(c,active,'機主收回、工作程序停止或分享條件不符')
                    stop = True
                else:
                    c.execute('UPDATE attempts SET lease_until=? WHERE id=?',(now+self.settings.lease_seconds,active['id']))
                    if body.stage:
                        c.execute("UPDATE jobs SET status=?,stage=?,progress=? WHERE id=?",('loading' if body.stage=='載入模型' else 'running',body.stage,body.progress,active['job_id']))
            elif body.attempt_id:
                stop = True
            return {'sharing':bool(node['sharing']),'within_schedule':self.in_schedule(node),'revoked':bool(node['revoked']),
                    'stop':stop,'lease_seconds':self.settings.lease_seconds,'server_time':now}

    def claim(self, node_id):
        now = self.clock()
        with self.transaction() as c:
            self.reap(c)
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            if not self.eligible(node) or c.execute('SELECT id FROM attempts WHERE node_id=? AND ended_at IS NULL',(node_id,)).fetchone():
                return None
            caps, telemetry = json.loads(node['capabilities']), json.loads(node['telemetry'])
            users = c.execute("SELECT u.* FROM users u WHERE u.enabled=1 AND EXISTS(SELECT 1 FROM jobs j WHERE j.user_id=u.id AND j.status IN ('queued','retrying')) ORDER BY u.last_dispatch,u.created_at,u.rowid").fetchall()
            selected = None
            for user in users:
                count = c.execute("SELECT count(*) FROM jobs WHERE user_id=? AND status IN ('loading','running')",(user['id'],)).fetchone()[0]
                if count >= user['max_running']:
                    continue
                # Preserve FIFO within each user's queue; incompatible head jobs wait for another GPU.
                job = c.execute("SELECT * FROM jobs WHERE user_id=? AND status IN ('queued','retrying') ORDER BY created_at,rowid LIMIT 1",(user['id'],)).fetchone()
                cap = caps.get(job['kind'],{})
                if cap.get('profile') != job['profile'] or cap.get('cuda_verified') is not True:
                    continue
                required = cap.get('peak_vram_mb',0)
                if telemetry.get('memory_free_mb') is not None and telemetry['memory_free_mb'] < required:
                    continue
                selected = job
                break
            if selected is None:
                return None
            attempt_id = uid()
            c.execute('INSERT INTO attempts(id,job_id,node_id,started_at,lease_until) VALUES(?,?,?,?,?)',(attempt_id,selected['id'],node_id,now,now+self.settings.lease_seconds))
            c.execute("UPDATE jobs SET status='loading',stage='載入模型',active_attempt_id=?,attempt_count=attempt_count+1,error=NULL,progress=NULL WHERE id=?",(attempt_id,selected['id']))
            seq = c.execute('SELECT coalesce(max(last_dispatch),0)+1 FROM users').fetchone()[0]
            c.execute('UPDATE users SET last_dispatch=? WHERE id=?',(seq,selected['user_id']))
            self.event(c,'dispatched',f'已分配至 {node["name"]}',user_id=selected['user_id'],node_owner_id=node['owner_id'],job_id=selected['id'],node_id=node_id)
            return {'attempt_id':attempt_id,'job_id':selected['id'],'kind':selected['kind'],'profile':selected['profile'],
                    'filename':selected['filename'],'input_bytes':selected['input_bytes'],'params':json.loads(selected['params']),
                    'lease_seconds':self.settings.lease_seconds,'input_url':f'/api/agent/attempts/{attempt_id}/input'}

    def current_attempt(self, c, node_id, attempt_id):
        self.reap(c)
        row = c.execute('SELECT a.*,j.status,j.active_attempt_id,j.user_id,j.kind,j.profile FROM attempts a JOIN jobs j ON a.job_id=j.id WHERE a.id=? AND a.node_id=?', (attempt_id,node_id)).fetchone()
        if not row or row['ended_at'] is not None or row['active_attempt_id']!=attempt_id or row['status'] not in ACTIVE:
            raise HTTPException(409,'工作租約已失效，請停止並捨棄此次輸出')
        return row

    def finish(self, node_id, attempt_id, artifacts, metrics):
        if metrics.get('cuda_verified') is not True:
            raise HTTPException(422,'結果缺少 GPU 執行證據')
        with self.transaction() as c:
            attempt = self.current_attempt(c,node_id,attempt_id)
            if metrics.get('profile') != attempt['profile']:
                raise HTTPException(422,'模型設定與工作不符')
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            if not self.eligible(node):
                raise HTTPException(409,'設備已停止分享')
            required = {'transcript.txt','subtitles.srt'} if attempt['kind']=='asr' else {'upscaled.png'}
            if len(artifacts)!=len(required) or {a['name'] for a in artifacts} != required:
                raise HTTPException(422,'結果檔案不完整')
            gpu_seconds=metrics.get('gpu_seconds')
            if isinstance(gpu_seconds,bool) or not isinstance(gpu_seconds,(int,float)) or not 0<gpu_seconds<86400:
                raise HTTPException(422,'缺少有效的 GPU 推論計時')
            used=c.execute('SELECT coalesce(sum(input_bytes),0) FROM jobs').fetchone()[0]+c.execute('SELECT coalesce(sum(size),0) FROM artifacts').fetchone()[0]
            if used+sum(a['size'] for a in artifacts)>self.settings.max_storage_bytes:
                raise HTTPException(507,'平台儲存空間已達上限')
            now = self.clock()
            for a in artifacts:
                c.execute('INSERT INTO artifacts(id,job_id,name,storage_key,media_type,size) VALUES(?,?,?,?,?,?)',
                          (a['id'],attempt['job_id'],a['name'],a['storage_key'],a['media_type'],a['size']))
            c.execute("UPDATE attempts SET ended_at=?,outcome='completed',gpu_verified=1,metrics=? WHERE id=?",(now,json.dumps(metrics),attempt_id))
            c.execute("UPDATE jobs SET status='completed',stage='處理完成',progress=1,completed_at=?,error=NULL WHERE id=?",(now,attempt['job_id']))
            self.event(c,'completed','工作已完成，結果可預覽及下載',user_id=attempt['user_id'],node_owner_id=node['owner_id'],job_id=attempt['job_id'],node_id=node_id)

    def fail(self,node_id,attempt_id,reason):
        with self.transaction() as c:
            attempt = self.current_attempt(c,node_id,attempt_id)
            self.end_attempt(c,attempt,reason[:400])

    def cancel_job(self, user, job_id):
        with self.transaction() as c:
            job = c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not job or (user['role']!='admin' and job['user_id']!=user['id']):
                raise HTTPException(404,'找不到工作')
            if job['status'] in ('completed','failed','cancelled'):
                return
            attempt = c.execute('SELECT * FROM attempts WHERE job_id=? AND ended_at IS NULL',(job_id,)).fetchone()
            if attempt:
                self.end_attempt(c,attempt,'使用者已取消工作',retry=False)
            else:
                c.execute("UPDATE jobs SET status='cancelled',stage='已取消',completed_at=? WHERE id=?",(self.clock(),job_id))
                self.event(c,'cancelled','使用者已取消工作',user_id=job['user_id'],job_id=job_id)

    def update_node(self,user,node_id,changes):
        with self.transaction() as c:
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            if not node or (user['role']!='admin' and node['owner_id']!=user['id']):
                raise HTTPException(404,'找不到設備')
            if node['revoked']:
                raise HTTPException(409,'設備已撤銷，無法再啟用')
            if changes:
                c.execute('UPDATE nodes SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),node_id))
            node = c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            if not node['sharing'] or node['revoked'] or not self.in_schedule(node):
                for a in c.execute('SELECT * FROM attempts WHERE node_id=? AND ended_at IS NULL',(node_id,)).fetchall():
                    self.end_attempt(c,a,'機主已收回設備' if not node['revoked'] else '管理者已撤銷設備')
            self.event(c,'node_updated',f'{node["name"]}：'+('開啟共享' if node['sharing'] and not node['revoked'] else '停止共享'),node_owner_id=node['owner_id'],node_id=node_id)

    def snapshot(self,user):
        with self.transaction() as c:
            self.reap(c)
            admin = user['role']=='admin'
            jobs = [dict(r) for r in c.execute('SELECT j.*,b.name batch_name,b.is_demo,u.display_name owner_name FROM jobs j JOIN batches b ON b.id=j.batch_id JOIN users u ON j.user_id=u.id WHERE b.archived=0 '+('' if admin else 'AND j.user_id=? ')+'ORDER BY j.created_at DESC,j.rowid DESC LIMIT 500',() if admin else (user['id'],))]
            for j in jobs:
                j.pop('input_key',None)
                j['params']=json.loads(j['params'])
                j['artifacts']=[dict(a) for a in c.execute('SELECT id,name,media_type,size FROM artifacts WHERE job_id=?',(j['id'],))]
                j['attempts']=[dict(a) for a in c.execute('SELECT a.id,a.node_id,n.name node_name,n.gpu_name,a.started_at,a.ended_at,a.outcome,a.error,a.gpu_verified,a.metrics FROM attempts a JOIN nodes n ON a.node_id=n.id WHERE a.job_id=? ORDER BY a.started_at',(j['id'],))]
                for a in j['attempts']:
                    a['metrics']=json.loads(a['metrics'])
                if j['status'] in PENDING:
                    j['waiting_reason']='等待相容且開啟共享的 GPU；系統會依使用者輪流分配'
            nodes=[]
            for r in c.execute('SELECT n.*,u.display_name owner_name FROM nodes n JOIN users u ON n.owner_id=u.id ORDER BY n.created_at'):
                n=dict(r); n.pop('token_hash'); n['capabilities']=json.loads(n['capabilities']); n['environment']=json.loads(n['environment']); n['telemetry']=json.loads(n['telemetry'])
                n['online']=self.clock()-n['last_seen']<self.settings.lease_seconds
                n['within_schedule']=self.in_schedule(n)
                active=c.execute('SELECT a.id,j.id job_id,j.kind,j.status,j.stage,j.user_id,j.filename FROM attempts a JOIN jobs j ON a.job_id=j.id WHERE a.node_id=? AND a.ended_at IS NULL',(n['id'],)).fetchone()
                n['current_job']=dict(active) if active else None
                if active and not admin and active['user_id']!=user['id']:
                    n['current_job']={'kind':active['kind'],'status':active['status'],'stage':active['stage']}
                totals=c.execute("SELECT count(*) completed_count,coalesce(sum(json_extract(metrics,'$.gpu_seconds')),0) compute_seconds FROM attempts WHERE node_id=? AND outcome='completed'",(n['id'],)).fetchone()
                n.update(dict(totals))
                if not admin and n['owner_id']!=user['id']:
                    for k in ('gpu_uuid','environment','schedule_start','schedule_end','owner_name'):
                        n.pop(k,None)
                nodes.append(n)
            events=[dict(e) for e in c.execute('SELECT * FROM events '+('' if admin else 'WHERE user_id=? OR node_owner_id=? ')+'ORDER BY id DESC LIMIT 80',() if admin else (user['id'],user['id']))]
            users=[self.public_user(r) for r in c.execute('SELECT * FROM users ORDER BY created_at')] if admin else []
            version=c.execute('SELECT coalesce(max(id),0) FROM events').fetchone()[0]
            return {'user':self.public_user(user),'jobs':jobs,'nodes':nodes,'events':events,'users':users,'version':version,'server_time':self.clock(),
                    'limits':{'max_file_mb':self.settings.max_file_bytes//1024//1024,'max_batch_files':self.settings.max_batch_files},'profiles':PROFILES}

