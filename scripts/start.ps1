param([int]$Port = 8765, [string]$Listen = '127.0.0.1', [string]$Cert = '', [string]$Key = '', [string]$Hosts = '127.0.0.1,localhost')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:RELAY_ALLOWED_HOSTS = $Hosts
$relayArgs = @('-m','relay.cli','serve','--host',$Listen,'--port',"$Port")
if ($Cert) { $relayArgs += @('--cert',$Cert,'--key',$Key) }
& .\.venv\Scripts\python.exe @relayArgs
