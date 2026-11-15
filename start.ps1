$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Missing .venv. Follow README setup steps first.'
}
if (-not $env:INKSHIELD_PORT) { $env:INKSHIELD_PORT = '8001' }
Write-Host "Open http://127.0.0.1:$env:INKSHIELD_PORT/"
& $python (Join-Path $PSScriptRoot 'server.py')
exit $LASTEXITCODE
