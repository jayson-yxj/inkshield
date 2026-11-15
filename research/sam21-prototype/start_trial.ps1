$ErrorActionPreference = 'Stop'
$trialRoot = $PSScriptRoot
$trialPython = Join-Path $trialRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $trialPython)) { throw 'Trial environment missing. Run setup first.' }
& $trialPython (Join-Path $trialRoot 'app.py')
exit $LASTEXITCODE
