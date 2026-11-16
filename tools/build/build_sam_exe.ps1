[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$CreateZip,
    [string]$OutputDirectory = 'dist\inkshield-20261110-r2',
    [string]$WorkDirectory = 'build\inkshield-20261110-r2'
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$projectRoot = $ProjectRoot
$python = Join-Path $projectRoot '.venv-sam-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Missing isolated .venv-sam-build. See docs/distribution/SAM_PACKAGING.md; existing environments are never modified.'
}
& $python -c "import sys,struct,platform; assert sys.platform == 'win32' and struct.calcsize('P') == 8 and platform.machine().lower() in ('amd64','x86_64'); import imageio_ffmpeg; from pathlib import Path; assert imageio_ffmpeg.__version__ == '0.6.0' and Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file(); import PyInstaller,webview,cv2,onnxruntime,fastapi,uvicorn,tkinter,av,torch,torchvision,sam2,hydra,omegaconf,iopath,huggingface_hub; assert torch.__version__ == '2.7.1+cu126'; assert torchvision.__version__ == '0.22.1+cu126'; assert onnxruntime.get_device() == 'CPU'; print('Build interpreter:',sys.executable); print('PyInstaller:',PyInstaller.__version__); print('Torch:',torch.__version__,'CUDA runtime:',torch.version.cuda,'GPU available:',torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'SAM packaging prerequisite check failed.' }
foreach ($relative in @('src/inkshield/desktop.py','src/inkshield/app_paths.py','src/inkshield/sam_engine.py','src/inkshield/sam_service.py','src/inkshield/web/index.html','src/inkshield/web/layers_ui.js','src/inkshield/web/workspace_ui.js','src/inkshield/web/workspace_ui.css','src/inkshield/mask_timeline.py','src/inkshield/mask_layers.py','src/inkshield/preview_video.py','src/inkshield/web/splash-preview.html','src/inkshield/web/tutorial-preview.html','assets\inkshield.ico','models\SAM21_SOURCE.md','models\SAM21_LICENSE.txt','models\SAM21_PROVENANCE.json','models\sam2.1_hiera_tiny.pt','docs/distribution/SAM_PACKAGING.md','packaging/pyinstaller/inkshield-sam.spec')) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $relative) -PathType Leaf)) { throw "Missing required asset: $relative" }
}
$checkpoint = Join-Path $projectRoot 'models\sam2.1_hiera_tiny.pt'
if ((Get-FileHash -LiteralPath $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne '7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69') { throw 'SAM checkpoint hash mismatch.' }
$distRoot = Join-Path $projectRoot $OutputDirectory
$workRoot = Join-Path $projectRoot $WorkDirectory
if (Test-Path -LiteralPath (Join-Path $distRoot 'Inkshield')) { throw "Output already exists; choose a new output directory: $distRoot" }
if ($CreateZip) { throw 'Release ZIP requires matrix, legacy and desktop gates; use package_sam_release.py after acceptance.' }
$buildArgs = @('-m','PyInstaller','--noconfirm','--distpath',$distRoot,'--workpath',$workRoot,'--log-level','INFO')
if ($Clean) { $buildArgs += '--clean' }
$buildArgs += (Join-Path $projectRoot 'packaging/pyinstaller/inkshield-sam.spec')
Push-Location $projectRoot
try {
    & $python @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
    $artifact = Join-Path $distRoot 'Inkshield\Inkshield.exe'
    if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) { throw 'Expected onedir Inkshield\Inkshield.exe was not created.' }
    Get-Item -LiteralPath $artifact | Select-Object FullName,Length,LastWriteTime
    Write-Output ("SHA256: {0}" -f (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash)
    if ($CreateZip) {
        # ZipFile supports large portable payloads without Compress-Archive's 2GB limitation.
        $zipPath = Join-Path $distRoot 'Inkshield-SAM-Windows-x64.zip'
        if (Test-Path -LiteralPath $zipPath) { throw "ZIP already exists; choose a new output directory: $zipPath" }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory((Join-Path $distRoot 'Inkshield'), $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)
        Get-Item -LiteralPath $zipPath | Select-Object FullName,Length,LastWriteTime
        Write-Output ("ZIP SHA256: {0}" -f (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash)
    }
} finally { Pop-Location }
