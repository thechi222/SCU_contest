from __future__ import annotations
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
import asyncio
import csv
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
import zipfile
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from PIL import Image, UnidentifiedImageError
from .config import Settings, PROFILES, PENDING
from .store import Store, uid
from .security import token_hash, new_token, verify_password, hash_password
from .models import Login, Pair, Heartbeat, NodeUpdate, Failure, UserCreate, UserUpdate, PasswordChange, ResetDemo

def create_app(settings: Settings | None = None, *, store: Store | None = None):
    settings = settings or Settings()
    store = store or Store(settings)

    @asynccontextmanager
    async def lifespan(app):
        async def maintenance():
            while True:
                await asyncio.to_thread(store.reap_expired)
                await asyncio.sleep(1)
        task=asyncio.create_task(maintenance())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app=FastAPI(title='算力接力站 API',version='0.1.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store
    from .limits import BodyLimit
    app.add_middleware(BodyLimit)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.allowed_hosts)

    @app.middleware('http')
    async def guard(request,call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
                # Vite serves same-origin development requests through its proxy.
                if not (not settings.secure_cookies and origin in ('http://127.0.0.1:5173','http://localhost:5173') and request.url.hostname in ('127.0.0.1','localhost')):
                    return JSONResponse({'detail':'不接受跨來源操作'},403)
            if not request.url.path.startswith('/api/agent/') and request.headers.get('x-relay-request')!='1':
                return JSONResponse({'detail':'缺少操作驗證標頭'},403)
            try:
                if int(request.headers.get('content-length','0'))>150*1024*1024:
                    return JSONResponse({'detail':'一次上傳總量不可超過 150 MB'},413)
            except ValueError:
                return JSONResponse({'detail':'上傳大小格式不正確'},400)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    def user(request:Request):
        return store.user_by_session(request.cookies.get('relay_session'))

    def admin(current=Depends(user)):
        if current['role']!='admin':
            raise HTTPException(403,'此操作需要管理者權限')
        return current

    def node(request:Request):
        auth=request.headers.get('authorization','')
        if not auth.startswith('Bearer '):
            raise HTTPException(401,'需要設備憑證')
        return store.node_by_token(auth[7:])

    def authorized_job(current,job_id):
        with store.connect() as c:
            job=c.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if not job or (current['role']!='admin' and job['user_id']!=current['id']):
            raise HTTPException(404,'找不到工作')
        return dict(job)

    def file_path(key):
        base=(settings.data_dir/'files').resolve()
        path=(base/key).resolve()
        if not path.is_relative_to(base):
            raise HTTPException(400,'無效的檔案位置')
        return path

    @app.get('/api/health')
    def health():
        return {'status':'ok','version':'0.1.0','gpu_execution':'agent_required'}

    @app.post('/api/auth/login')
    def login(body:Login,request:Request):
        key=token_hash((request.client.host if request.client else '')+'|'+body.username.lower())
        now=store.clock()
        with store.transaction() as c:
            failed=c.execute('SELECT * FROM login_attempts WHERE key=?',(key,)).fetchone()
            if failed and failed['window_start']>now-300 and failed['failures']>=10:
                raise HTTPException(429,'嘗試次數過多，請五分鐘後再試')
            row=c.execute('SELECT * FROM users WHERE username=?',(body.username,)).fetchone()
            valid=row and row['enabled'] and verify_password(body.password,row['password_hash'])
            if not valid:
                count=failed['failures']+1 if failed and failed['window_start']>now-300 else 1
                start=failed['window_start'] if failed and failed['window_start']>now-300 else now
                c.execute('INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)',(key,count,start))
            else:
                c.execute('DELETE FROM login_attempts WHERE key=?',(key,))
                token=new_token()
                c.execute('INSERT INTO sessions VALUES(?,?,?)',(token_hash(token),row['id'],now+settings.session_seconds))
        if not valid:
            raise HTTPException(401,'帳號或密碼不正確，或帳號已停用')
        response=JSONResponse({'user':store.public_user(row)})
        response.set_cookie('relay_session',token,httponly=True,samesite='strict',secure=settings.secure_cookies,max_age=settings.session_seconds,path='/')
        return response

    @app.post('/api/auth/logout')
    def logout(request:Request):
        with store.transaction() as c:
            c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies.get('relay_session','')),))
        response=JSONResponse({'ok':True}); response.delete_cookie('relay_session',path='/'); return response

    @app.post('/api/auth/password')
    def change_password(body:PasswordChange,current=Depends(user)):
        if not verify_password(body.current_password,current['password_hash']):
            raise HTTPException(400,'目前密碼不正確')
        with store.transaction() as c:
            c.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(body.new_password),current['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?',(current['id'],))
        return {'ok':True,'message':'密碼已更新，請重新登入'}

    @app.get('/api/state')
    def state(current=Depends(user)):
        return store.snapshot(current)

    @app.get('/api/events')
    async def event_stream(request:Request,current=Depends(user)):
        async def stream():
            while not await request.is_disconnected():
                try:
                    fresh=store.user_by_session(request.cookies.get('relay_session'))
                    data=await asyncio.to_thread(store.snapshot,fresh)
                except HTTPException:
                    yield 'event: expired\ndata: {}\n\n'; return
                yield 'event: state\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n'
                await asyncio.sleep(2)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no','Cache-Control':'no-store'})

    async def save_upload(upload,key,max_bytes):
        size=0; path=file_path(key); path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with path.open('wb') as f:
                while chunk:=await upload.read(1024*1024):
                    size+=len(chunk)
                    if size>max_bytes:
                        raise HTTPException(413,'檔案超過大小限制')
                    f.write(chunk)
            if not size:
                raise HTTPException(422,'檔案是空的')
            return size
        except BaseException:
            path.unlink(missing_ok=True); raise

    def validate_image(path):
        try:
            with Image.open(path) as image:
                if image.format not in ('JPEG','PNG','WEBP') or image.width>2048 or image.height>2048:
                    raise HTTPException(422,'圖片需為 PNG、JPEG 或 WebP，寬高各不超過 2048 像素')
                image.verify()
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError):
            raise HTTPException(422,'圖片無法讀取，請選擇有效的圖片')

    @app.post('/api/batches')
    async def create_batch(request:Request,current=Depends(user)):
        form=await request.form(max_files=settings.max_batch_files,max_fields=6,max_part_size=settings.max_file_bytes)
        kind=str(form.get('kind','')); name=str(form.get('name','新任務')).strip()[:80]
        if kind not in PROFILES:
            raise HTTPException(422,'請選擇支援的任務類型')
        files=form.getlist('files')
        if not files or len(files)>settings.max_batch_files or any(not hasattr(f,'read') for f in files):
            raise HTTPException(422,f'請選擇 1–{settings.max_batch_files} 個檔案')
        batch_id=uid(); saved=[]
        try:
            for upload in files:
                filename=Path((upload.filename or 'input').replace('\\','/')).name
                filename=re.sub(r'[\x00-\x1f\x7f]','',filename)[:160] or 'input'
                suffix=Path(filename).suffix.lower()
                allowed={'.png','.jpg','.jpeg','.webp'} if kind=='upscale' else {'.wav','.mp3','.m4a','.flac','.ogg','.mp4','.webm'}
                if suffix not in allowed:
                    raise HTTPException(422,'檔案格式不支援：'+filename)
                job_id=uid(); key=f'inputs/{job_id}{suffix}'
                size=await save_upload(upload,key,settings.max_file_bytes)
                saved.append({'id':job_id,'key':key,'filename':filename,'size':size})
                if kind=='upscale': validate_image(file_path(key))
            if sum(f['size'] for f in saved)>150*1024*1024:
                raise HTTPException(413,'一次提交總量不可超過 150 MB')
            now=store.clock()
            with store.transaction() as c:
                fresh=c.execute('SELECT * FROM users WHERE id=?',(current['id'],)).fetchone()
                if not fresh['enabled']: raise HTTPException(403,'帳號已停用')
                daily=c.execute('SELECT count(*) FROM jobs WHERE user_id=? AND created_at>=?',(current['id'],now-86400)).fetchone()[0]
                if daily+len(saved)>fresh['daily_limit']:
                    raise HTTPException(429,'已達最近 24 小時的工作提交額度')
                used=c.execute('SELECT coalesce(sum(input_bytes),0) FROM jobs').fetchone()[0]+c.execute('SELECT coalesce(sum(size),0) FROM artifacts').fetchone()[0]
                if used+sum(f['size'] for f in saved)>settings.max_storage_bytes:
                    raise HTTPException(507,'平台儲存空間已達上限，請聯絡管理者')
                c.execute('INSERT INTO batches(id,user_id,name,kind,is_demo,created_at) VALUES(?,?,?,?,?,?)',(batch_id,current['id'],name or '新任務',kind,int(form.get('is_demo')=='true'),now))
                for f in saved:
                    c.execute('INSERT INTO jobs(id,batch_id,user_id,kind,profile,filename,input_key,input_bytes,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                              (f['id'],batch_id,current['id'],kind,PROFILES[kind],f['filename'],f['key'],f['size'],now))
                    store.event(c,'queued',f['filename']+' 已加入佇列',user_id=current['id'],job_id=f['id'])
            return {'batch_id':batch_id,'job_ids':[f['id'] for f in saved]}
        except BaseException:
            for f in saved: file_path(f['key']).unlink(missing_ok=True)
            raise
        finally:
            await form.close()

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id:str,current=Depends(user)):
        store.cancel_job(current,job_id); return {'ok':True}

    @app.post('/api/jobs/{job_id}/retry')
    def retry(job_id:str,current=Depends(user)):
        job=authorized_job(current,job_id)
        if job['status'] not in ('failed','cancelled','completed'):
            raise HTTPException(409,'工作尚在處理中')
        new_id,batch_id=uid(),uid(); key=f'inputs/{new_id}{Path(job["filename"]).suffix.lower()}'
        source=file_path(job['input_key'])
        if not source.is_file():raise HTTPException(404,'原始檔案已不存在，請重新上傳')
        target=file_path(key); shutil.copyfile(source,target)
        try:
            with store.transaction() as c:
                count=c.execute('SELECT count(*) FROM jobs WHERE user_id=? AND created_at>=?',(current['id'],store.clock()-86400)).fetchone()[0]
                if count>=current['daily_limit']:raise HTTPException(429,'已達工作提交額度')
                used=c.execute('SELECT coalesce(sum(input_bytes),0) FROM jobs').fetchone()[0]+c.execute('SELECT coalesce(sum(size),0) FROM artifacts').fetchone()[0]
                if used+job['input_bytes']>settings.max_storage_bytes:raise HTTPException(507,'平台儲存空間已達上限')
                demo=c.execute('SELECT is_demo FROM batches WHERE id=?',(job['batch_id'],)).fetchone()[0]
                c.execute('INSERT INTO batches(id,user_id,name,kind,is_demo,created_at) VALUES(?,?,?,?,?,?)',(batch_id,current['id'],'重新提交 · '+job['filename'][:60],job['kind'],demo,store.clock()))
                c.execute('INSERT INTO jobs(id,batch_id,user_id,kind,profile,filename,input_key,input_bytes,params,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (new_id,batch_id,current['id'],job['kind'],job['profile'],job['filename'],key,job['input_bytes'],job['params'],store.clock()))
                store.event(c,'queued','已重新提交工作',user_id=current['id'],job_id=new_id)
            return {'job_id':new_id,'batch_id':batch_id}
        except BaseException:
            target.unlink(missing_ok=True);raise

    @app.get('/api/jobs/{job_id}/input')
    def input_file(job_id:str,current=Depends(user)):
        job=authorized_job(current,job_id)
        path=file_path(job['input_key'])
        if not path.is_file():raise HTTPException(404,'找不到原始檔案')
        return FileResponse(path,media_type=mimetypes.guess_type(job['filename'])[0] or 'application/octet-stream',filename=job['filename'],content_disposition_type='inline')

    @app.get('/api/artifacts/{artifact_id}')
    def artifact_file(artifact_id:str,download:bool=False,current=Depends(user)):
        with store.connect() as c: a=c.execute('SELECT * FROM artifacts WHERE id=?',(artifact_id,)).fetchone()
        if not a:raise HTTPException(404,'找不到結果')
        authorized_job(current,a['job_id']); path=file_path(a['storage_key'])
        if not path.is_file():raise HTTPException(404,'找不到結果檔案')
        return FileResponse(path,media_type=a['media_type'],filename=a['name'],content_disposition_type='attachment' if download else 'inline')

    @app.get('/api/batches/{batch_id}/download')
    def batch_download(batch_id:str,current=Depends(user)):
        with store.connect() as c:
            b=c.execute('SELECT * FROM batches WHERE id=?',(batch_id,)).fetchone()
            if not b or (current['role']!='admin' and b['user_id']!=current['id']):raise HTTPException(404,'找不到批次')
            rows=c.execute('SELECT a.*,j.filename FROM artifacts a JOIN jobs j ON a.job_id=j.id WHERE j.batch_id=?',(batch_id,)).fetchall()
        if not rows:raise HTTPException(409,'尚無可下載的成果')
        # Store the archive on disk to avoid buffering large batches in memory.
        archive_dir=settings.data_dir/'downloads'; archive_dir.mkdir(exist_ok=True)
        path=archive_dir/(uid()+'.zip')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for a in rows:
                z.write(file_path(a['storage_key']),a['job_id'][:8]+'/'+Path(a['filename']).stem[:70]+'-'+a['name'])
        from starlette.background import BackgroundTask
        return FileResponse(path,filename=f'relay-{batch_id[:8]}.zip',background=BackgroundTask(path.unlink,missing_ok=True))

    @app.post('/api/pairing-codes')
    def pairing(current=Depends(user)):
        return store.issue_pairing_code(current['id'])

    @app.patch('/api/nodes/{node_id}')
    def change_node(node_id:str,body:NodeUpdate,current=Depends(user)):
        changes=body.model_dump(exclude_unset=True)
        if 'revoked' in changes and current['role']!='admin':raise HTTPException(403,'撤銷設備需要管理者權限')
        if any(changes.get(k) is None for k in ('name','sharing','revoked','utc_offset_minutes') if k in changes):
            raise HTTPException(422,'此欄位不可為空')
        if ('schedule_start' in changes)!=('schedule_end' in changes) or (bool(changes.get('schedule_start'))!=bool(changes.get('schedule_end'))):
            raise HTTPException(422,'請同時設定或清除開始與結束時間')
        store.update_node(current,node_id,changes);return {'ok':True}

    @app.delete('/api/admin/nodes/{node_id}')
    def forget_node(node_id:str,current=Depends(admin)):
        with store.transaction() as c:
            n=c.execute('SELECT * FROM nodes WHERE id=?',(node_id,)).fetchone()
            if not n or not n['revoked']:raise HTTPException(409,'請先撤銷設備')
            # Preserve historical attempts, but free the physical identity for re-pairing.
            c.execute('UPDATE nodes SET gpu_uuid=? WHERE id=?',('retired-'+uid(),node_id))
        return {'ok':True}

    @app.post('/api/admin/users')
    def create_user(body:UserCreate,current=Depends(admin)):
        try: user_id=store.create_user(body.username,body.password,body.display_name,body.role)
        except sqlite3.IntegrityError:raise HTTPException(409,'帳號已存在')
        return {'user_id':user_id}

    @app.patch('/api/admin/users/{user_id}')
    def change_user(user_id:str,body:UserUpdate,current=Depends(admin)):
        changes=body.model_dump(exclude_none=True)
        if user_id==current['id'] and changes.get('enabled') is False:raise HTTPException(400,'無法停用自己的帳號')
        with store.transaction() as c:
            if not c.execute('SELECT id FROM users WHERE id=?',(user_id,)).fetchone():raise HTTPException(404,'找不到帳號')
            if changes:c.execute('UPDATE users SET '+','.join(k+'=?' for k in changes)+' WHERE id=?',(*changes.values(),user_id))
            if changes.get('enabled') is False:
                c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
                c.execute('UPDATE nodes SET sharing=0 WHERE owner_id=?',(user_id,))
                for a in c.execute('SELECT a.* FROM attempts a JOIN jobs j ON a.job_id=j.id JOIN nodes n ON a.node_id=n.id WHERE a.ended_at IS NULL AND (j.user_id=? OR n.owner_id=?)',(user_id,user_id)).fetchall():
                    store.end_attempt(c,a,'帳號已停用',retry=False if c.execute('SELECT user_id FROM jobs WHERE id=?',(a['job_id'],)).fetchone()[0]==user_id else True)
                c.execute("UPDATE jobs SET status='cancelled',stage='帳號已停用',completed_at=? WHERE user_id=? AND status IN ('queued','retrying')",(store.clock(),user_id))
        return {'ok':True}

    @app.post('/api/admin/demo/reset')
    def reset_demo(body:ResetDemo,current=Depends(admin)):
        with store.transaction() as c:
            for batch_id in body.batch_ids:
                b=c.execute('SELECT * FROM batches WHERE id=?',(batch_id,)).fetchone()
                if not b or not b['is_demo']:raise HTTPException(400,'只能重置指定的示範批次')
            for batch_id in body.batch_ids:
                for a in c.execute('SELECT a.* FROM attempts a JOIN jobs j ON a.job_id=j.id WHERE j.batch_id=? AND a.ended_at IS NULL',(batch_id,)).fetchall():
                    store.end_attempt(c,a,'示範工作已重置',retry=False)
                c.execute("UPDATE jobs SET status='cancelled',stage='示範工作已重置',completed_at=? WHERE batch_id=? AND status IN ('queued','retrying')",(store.clock(),batch_id))
                c.execute('UPDATE batches SET archived=1 WHERE id=?',(batch_id,))
            store.event(c,'demo_reset',f'已封存 {len(body.batch_ids)} 個指定示範批次')
        return {'ok':True,'archived_batches':body.batch_ids,'files_preserved':True}

    @app.post('/api/admin/demo/restore')
    def restore_demo(current=Depends(admin)):
        with store.transaction() as c:
            count=c.execute('UPDATE batches SET archived=0 WHERE is_demo=1 AND archived=1').rowcount
        return {'ok':True,'restored':count}

    @app.get('/api/admin/report')
    def report(current=Depends(admin)):
        snapshot=store.snapshot(current)
        buffer=io.StringIO(newline=''); writer=csv.writer(buffer)
        writer.writerow(['工作編號','檔名','類型','狀態','嘗試次數','完整耗時秒','節點','GPU','GPU驗證','實際執行秒'])
        for j in snapshot['jobs']:
            a=j['attempts'][-1] if j['attempts'] else {}
            values=[j['id'],j['filename'],j['kind'],j['status'],j['attempt_count'],round(j['completed_at']-j['created_at'],2) if j['completed_at'] else '',a.get('node_name',''),a.get('gpu_name',''),bool(a.get('gpu_verified')),a.get('metrics',{}).get('gpu_seconds','')]
            writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
        return Response('\ufeff'+buffer.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="relay-report.csv"'})

    @app.post('/api/agent/pair')
    def pair(body:Pair):return store.pair(body)

    @app.post('/api/agent/heartbeat')
    def heartbeat(body:Heartbeat,current=Depends(node)):return store.heartbeat(current['id'],body)

    @app.post('/api/agent/claim')
    def claim(current=Depends(node)):return {'assignment':store.claim(current['id'])}

    @app.get('/api/agent/attempts/{attempt_id}/input')
    def agent_input(attempt_id:str,current=Depends(node)):
        with store.transaction() as c:
            attempt=store.current_attempt(c,current['id'],attempt_id)
            j=c.execute('SELECT * FROM jobs WHERE id=?',(attempt['job_id'],)).fetchone()
        return FileResponse(file_path(j['input_key']),filename=j['filename'],media_type='application/octet-stream')

    @app.post('/api/agent/attempts/{attempt_id}/fail')
    def agent_fail(attempt_id:str,body:Failure,current=Depends(node)):
        store.fail(current['id'],attempt_id,body.reason);return {'ok':True}

    @app.post('/api/agent/attempts/{attempt_id}/complete')
    async def agent_complete(attempt_id:str,request:Request,current=Depends(node)):
        with store.transaction() as c:
            attempt=store.current_attempt(c,current['id'],attempt_id)
            job=dict(c.execute('SELECT * FROM jobs WHERE id=?',(attempt['job_id'],)).fetchone())
        form=await request.form(max_files=3,max_fields=1,max_part_size=50*1024*1024)
        staged=[]
        try:
            try:metrics=json.loads(str(form.get('metrics','{}')))
            except (ValueError,TypeError):raise HTTPException(422,'無效的執行紀錄')
            if not isinstance(metrics,dict) or len(json.dumps(metrics))>8192:raise HTTPException(422,'執行紀錄格式不正確')
            for upload in form.getlist('files'):
                name=getattr(upload,'filename','')
                media={'transcript.txt':'text/plain; charset=utf-8','subtitles.srt':'text/plain; charset=utf-8','upscaled.png':'image/png'}.get(name)
                if not media:raise HTTPException(422,'不接受的結果檔案')
                artifact_id=uid(); key=f'results/{attempt_id}/{artifact_id}-{name}'
                size=await save_upload(upload,key,50*1024*1024)
                staged.append({'id':artifact_id,'name':name,'storage_key':key,'media_type':media,'size':size})
                if name.endswith('.png'):
                    try:
                        with Image.open(file_path(key)) as im:
                            if im.format!='PNG' or max(im.size)>4096:raise ValueError('invalid output')
                            with Image.open(file_path(job['input_key'])) as source:
                                if im.size!=(source.width*2,source.height*2):raise ValueError('output must be 2x')
                            im.verify()
                    except (ValueError,OSError,Image.DecompressionBombError):raise HTTPException(422,'輸出圖片無效')
                else:
                    if size>5*1024*1024:raise HTTPException(422,'文字結果過大')
                    try:file_path(key).read_text(encoding='utf-8')
                    except UnicodeError:raise HTTPException(422,'文字需使用 UTF-8')
            store.finish(current['id'],attempt_id,staged,metrics)
            return {'ok':True}
        except BaseException:
            for a in staged:file_path(a['storage_key']).unlink(missing_ok=True)
            raise
        finally:await form.close()

    if settings.frontend_dir.is_dir():
        app.mount('/assets',StaticFiles(directory=settings.frontend_dir/'assets'),name='assets')
        @app.get('/favicon.svg')
        def favicon():return FileResponse(settings.frontend_dir/'favicon.svg')
        @app.get('/{path:path}')
        def frontend(path:str):
            if path.startswith('api/'):
                raise HTTPException(404,'找不到 API')
            return FileResponse(settings.frontend_dir/'index.html',media_type='text/html')
    return app
