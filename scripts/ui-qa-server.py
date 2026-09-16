"""Disposable loopback UI verification server; never used by deployment scripts."""
import tempfile
from pathlib import Path
import uvicorn
from relay.app import create_app
from relay.config import Settings
from relay.store import Store

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='relay-ui-qa-') as directory:
        settings=Settings(data_dir=Path(directory))
        store=Store(settings)
        store.create_user('uiqa','local-ui-check-only','介面驗證','admin')
        uvicorn.run(create_app(settings,store=store),host='127.0.0.1',port=8766)
