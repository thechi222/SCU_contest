param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& $Python -m venv .venv
if ($LASTEXITCODE) { throw 'Python 3.11+ is required. Use -Python with the Python executable path.' }
& .\.venv\Scripts\python.exe -m pip install -c requirements.lock -e '.[dev,agent,deploy]'
if ($LASTEXITCODE) { throw 'Python dependency installation failed' }
Push-Location frontend
try {
    npm ci
    if ($LASTEXITCODE) { throw 'npm ci failed' }
    npm run build
    if ($LASTEXITCODE) { throw 'UI build failed' }
} finally { Pop-Location }
& .\.venv\Scripts\python.exe -m relay.cli init
Write-Output 'Ready. Start with scripts/start.ps1. Accounts: data/initial-accounts.md'
