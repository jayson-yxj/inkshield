$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$borrowed = Join-Path (Split-Path $root -Parent) 'adaface-comparison\.venv'
$python = Join-Path $root '.venv\Scripts\python.exe'
$borrowedPython = Join-Path $borrowed 'Scripts\python.exe'
if (!(Test-Path $borrowedPython)) { throw 'Read-only adaface CPU torch environment is required for this machine-specific setup.' }
if (!(Test-Path $python)) { & uv venv --python $borrowedPython (Join-Path $root '.venv'); if ($LASTEXITCODE) { throw 'venv creation failed' } }
# ASCII Python escapes avoid Windows .pth legacy code-page decoding of Chinese paths.
$borrowedSite = Join-Path $borrowed 'Lib\site-packages'
$env:SAM_BORROWED_SITE = $borrowedSite
& $python -c "import os,pathlib; p=pathlib.Path(r'$root')/'.venv/Lib/site-packages/borrowed_torch.pth'; p.write_text('import sys; sys.path.append('+ascii(os.environ['SAM_BORROWED_SITE'])+')\n',encoding='ascii')"
& uv pip install --python $python hydra-core==1.3.2 iopath==0.1.10 pillow==13.0.0 tqdm==4.70.1 opencv-python==5.0.0.93 fastapi==0.162.2 uvicorn==0.54.0 python-multipart==0.0.33 av==18.1.0 httpx==0.28.1 pywebview==6.2.1
if ($LASTEXITCODE) { throw 'Dependency install failed' }
& uv pip install --python $python --no-deps --index-url https://download.pytorch.org/whl/cpu torchvision==0.29.2+cpu
if ($LASTEXITCODE) { throw 'CPU torchvision install failed' }
$env:SAM2_BUILD_CUDA = '0'
& uv pip install --python $python --no-deps --no-build-isolation -e (Join-Path $root 'vendor\sam2')
if ($LASTEXITCODE) { throw 'Official SAM2 CPU install failed' }
& $python (Join-Path $root 'fetch_checkpoint.py')
if ($LASTEXITCODE) { throw 'Checkpoint verification failed' }
& $python -c "import torch,torchvision,sam2; print(torch.__version__,torchvision.__version__);print(torch.__file__);print(sam2.__file__)"
if ($LASTEXITCODE) { throw 'Import verification failed' }
