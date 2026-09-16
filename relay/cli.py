import argparse
import json
import os
import secrets
from pathlib import Path
import uvicorn
from .config import Settings
from .store import Store

def main():
    parser=argparse.ArgumentParser(description='算力接力站中央服務')
    parser.add_argument('--data-dir',type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init',help='建立測試帳號，隨機密碼存於 data/initial-accounts.md')
    init.add_argument('--admin-password',default=os.getenv('RELAY_ADMIN_PASSWORD'))
    serve=sub.add_parser('serve');serve.add_argument('--host',default='127.0.0.1');serve.add_argument('--port',type=int,default=8765)
    serve.add_argument('--cert');serve.add_argument('--key')
    args=parser.parse_args(); settings=Settings()
    if args.data_dir:settings.data_dir=args.data_dir.resolve()
    if args.command=='init':
        store=Store(settings)
        with store.connect() as c:
            if c.execute('SELECT count(*) FROM users').fetchone()[0]:
                print('Accounts already exist; no changes made.');return
        entries=[]
        for name,display,role in [('admin','平台管理者','admin'),('student','同學 A','member'),('provider','設備提供者','member')]:
            password=args.admin_password if name=='admin' and args.admin_password else secrets.token_urlsafe(15)
            store.create_user(name,password,display,role)
            entries.append(f'| {name} | {display} | `{password}` |')
        path=settings.data_dir/'initial-accounts.md'
        path.write_text('# 本機初始帳號\n\n請保管此檔案，勿提交 Git 或公開分享。登入後可在設定頁修改密碼。\n\n| 帳號 | 名稱 | 隨機密碼 |\n|---|---|---|\n'+'\n'.join(entries)+'\n',encoding='utf-8')
        print(f'Created 3 accounts. Credentials: {path}')
    else:
        from .app import create_app
        if args.host not in ('127.0.0.1','localhost') and not (args.cert and args.key):
            parser.error('LAN hosting requires --cert and --key. Use scripts/create-certs.py first.')
        if args.cert:settings.secure_cookies=True
        uvicorn.run(create_app(settings),host=args.host,port=args.port,ssl_certfile=args.cert,ssl_keyfile=args.key,workers=1)

if __name__=='__main__':main()
