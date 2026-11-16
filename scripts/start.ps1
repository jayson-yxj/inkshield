$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Missing .venv. Follow README setup steps first.'
}
# Match the original service-only launcher; explicit caller options take precedence.
$launchArgs = @('--serve-only')
if ($args -notcontains '--port') {
    $port = if ($env:INKSHIELD_PORT) { $env:INKSHIELD_PORT } else { '8001' }
    $launchArgs += @('--port', $port)
}
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
& $python -m inkshield @launchArgs @args
exit $LASTEXITCODE
