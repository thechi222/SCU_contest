"""Package public project files using an allowlist; credentials never included."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'release';out.mkdir(exist_ok=True)
target=out/'compute-relay-demo.zip'
folders=['relay','agent','workers','frontend/src','frontend/public','frontend/dist','scripts','tests','docs','demo-assets']
files=['README.md','pyproject.toml','requirements.lock','THIRD_PARTY.md','.dockerignore','.gitignore','frontend/package.json','frontend/package-lock.json','frontend/index.html','frontend/tsconfig.json','frontend/vite.config.ts']
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    paths=[ROOT/f for f in files]+[p for folder in folders for p in (ROOT/folder).rglob('*') if p.is_file()]
    for path in paths:
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.key','.pem'):
            archive.write(path,path.relative_to(ROOT))
print(target)
