[CmdletBinding()]
param([switch]$Clean, [string]$OutputDirectory = 'dist\face-selection-trial', [string]$WorkDirectory = 'build\face-selection-trial')
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Missing existing project .venv. Create/install it explicitly before building.'
}
& $python -c "import sys,struct,platform; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and platform.machine().lower() in ('amd64','x86_64'), 'Native Windows x64 Python required'; import PyInstaller,webview,cv2,onnxruntime,fastapi,uvicorn,tkinter,av; print('Build interpreter:',sys.executable); print('PyInstaller:',PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Packaging prerequisite check failed. No packages were changed.' }
foreach ($relative in @('desktop.py','app_paths.py','index.html','splash-preview.html','assets\inkshield.ico','models\SOURCE.md','models\HYPERLPR_SOURCE.md','models\det_500m.onnx','models\w600k_mbf.onnx','models\FACE_SOURCE.md','models\y5fu_320x_sim.onnx','PACKAGING_REPORT.md','requirements-packaging.lock.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative) -PathType Leaf)) { throw "Missing required asset: $relative" }
}
$distRoot = Join-Path $projectRoot $OutputDirectory
$workRoot = Join-Path $projectRoot $WorkDirectory
$buildArgs = @('-m','PyInstaller','--noconfirm','--distpath',$distRoot,'--workpath',$workRoot,'--log-level','INFO')
if ($Clean) { $buildArgs += '--clean' }
$buildArgs += (Join-Path $projectRoot 'inkshield.spec')
Push-Location $projectRoot
try {
    & $python @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    $artifact = Join-Path $distRoot 'Inkshield.exe'
    if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) { throw 'Expected dist\Inkshield.exe was not created.' }
    Get-Item -LiteralPath $artifact | Select-Object FullName,Length,LastWriteTime
    $artifactHash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
    Write-Output ("SHA256: {0}" -f $artifactHash.Hash)
} finally { Pop-Location }
