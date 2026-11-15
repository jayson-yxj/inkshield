# -*- mode: python ; coding: utf-8 -*-
"""Native Windows x64 portable SAM 2.1 CPU/CUDA onedir build."""
from pathlib import Path
from importlib import metadata
import platform
import os
import struct
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata, collect_all

ROOT = Path(SPECPATH).resolve()
VENDOR = ROOT / 'research/sam21-prototype/vendor/sam2'
if sys.platform != 'win32' or struct.calcsize('P') != 8 or platform.machine().lower() not in ('amd64', 'x86_64'):
    raise RuntimeError('Inkshield must be built using native Windows x64 Python.')

asset_names = [
    'index.html', 'splash-preview.html', 'tutorial-preview.html', 'assets/inkshield.ico',
    'layers_ui.js', 'workspace_ui.js', 'workspace_ui.css',
    'models/det_500m.onnx', 'models/w600k_mbf.onnx', 'models/FACE_SOURCE.md',
    'models/INSIGHTFACE_LICENSE.txt', 'models/y5fu_320x_sim.onnx', 'models/SOURCE.md',
    'models/HYPERLPR_SOURCE.md', 'models/sam2.1_hiera_tiny.pt',
    'models/SAM21_SOURCE.md', 'models/SAM21_PROVENANCE.json', 'models/SAM21_LICENSE.txt',
    'PACKAGING_REPORT.md', 'PACKAGING_DEPENDENCIES.json',
    'requirements-packaging.lock.txt', 'AUDIO_DEPENDENCIES.md', 'SAM_PACKAGING.md',
]
datas = []
for name in asset_names:
    source = ROOT / name
    if not source.is_file():
        raise FileNotFoundError(source)
    datas.append((str(source), str(Path(name).parent)))

# Retain installed wheel notices, including Torch/CUDA, PyAV/FFmpeg and NumPy.
for dist in metadata.distributions():
    label = dist.metadata.get('Name', 'unknown').replace('/', '_').replace('\\', '_')
    for item in dist.files or []:
        leaf = Path(str(item)).name.lower()
        parts = [part.lower() for part in Path(str(item)).parts]
        if (leaf.startswith(('license', 'licence', 'copying', 'notice', 'third_party_notices'))
                or 'licenses' in parts) and not leaf.endswith(('.py', '.pyc', '.pyd', '.dll')):
            source = Path(dist.locate_file(item))
            relative_parent = Path(str(item)).parent
            if source.is_file() and '..' not in relative_parent.parts:
                datas.append((str(source), str(Path('third_party_licenses') / label / relative_parent)))
python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.is_file():
    datas.append((str(python_license), 'third_party_licenses/CPython'))
# Vendor license is also kept explicitly: editable wheel metadata need not copy it.
datas.append((str(VENDOR / 'LICENSE'), 'third_party_licenses/SAM-2'))
# Formal engine checks this physical vendor path before importing. Keep just the
# runtime package source/configs, not the repository, .git, demos or checkpoints.
for source in (VENDOR / 'sam2').rglob('*'):
    if source.is_file() and '__pycache__' not in source.parts and source.suffix in ('.py', '.yaml', '.yml'):
        destination = Path('vendor/sam2/sam2') / source.relative_to(VENDOR / 'sam2').parent
        datas.append((str(source), str(destination)))
for package in ('onnxruntime', 'fastapi', 'uvicorn', 'pywebview', 'pythonnet',
                'clr_loader', 'torch', 'torchvision', 'SAM-2', 'hydra-core',
                'omegaconf', 'iopath', 'huggingface-hub'):
    datas += copy_metadata(package)

# Pin the modern, compatible System32 VC runtime family, as in the original spec.
system32 = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32'
vc_names = ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll',
            'msvcp140_1.dll', 'msvcp140_2.dll', 'concrt140.dll')
for name in vc_names:
    if not (system32 / name).is_file():
        raise FileNotFoundError(f'Install the current Microsoft VC++ x64 Redistributable before building: {name}')
binaries = [(str(system32 / name), '.') for name in vc_names]
binaries += collect_dynamic_libs('onnxruntime') + collect_dynamic_libs('cv2')
# PyInstaller's torch/torchvision hooks remain enabled. Explicit collection also
# retains cu126 wheel DLLs (cudart, cublas, cuDNN etc.) beside torch's own DLLs.
binaries += collect_dynamic_libs('torch') + collect_dynamic_libs('torchvision')
os.environ['PATH'] = os.pathsep.join((str(Path(sys.executable).parent),
    str(Path(sys.base_prefix)), str(system32), str(system32.parent)))
hiddenimports = [
    'server', 'app_paths', 'cpu_runtime', 'masking', 'plate_detector',
    'face_detector', 'identity_gallery', 'scrfd', 'sam_engine', 'sam_service',
    'mask_timeline', 'mask_layers', 'preview_video',
    'uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
    'uvicorn.lifespan.on', 'uvicorn.lifespan.off', 'python_multipart',
    'webview.platforms.winforms', 'webview.platforms.edgechromium',
    'pythonnet', 'clr', 'clr_loader', '_cffi_backend',
]
# Hydra discovers target classes and YAML configuration at runtime. Collect SAM2
# and Hydra resources explicitly rather than relying only on static imports.
for package in ('sam2', 'hydra', 'omegaconf', 'iopath'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

# Protected-video encoding uses the wheel-provided FFmpeg executable.
ff_datas, ff_binaries, ff_hidden = collect_all('imageio_ffmpeg')
datas += ff_datas + copy_metadata('imageio-ffmpeg')
binaries += ff_binaries
hiddenimports += ff_hidden

# PyAV's wheel-vendored FFmpeg also stays included for decoding.
av_datas, av_binaries, av_hidden = collect_all('av')
datas += av_datas + copy_metadata('av')
binaries += av_binaries
av_dist = metadata.distribution('av')
for item in av_dist.files or []:
    if str(item).replace('\\', '/').startswith('av.libs/') and str(item).lower().endswith('.dll'):
        binaries.append((str(av_dist.locate_file(item)), 'av.libs'))
hiddenimports += av_hidden

a = Analysis(
    [str(ROOT / 'desktop.py')], pathex=[str(ROOT), str(VENDOR)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['pytest', 'IPython', 'notebook', 'matplotlib',
                                'tensorflow', 'mediapipe', 'research',
                                'webview.platforms.qt', 'webview.platforms.gtk',
                                'webview.platforms.cocoa', 'webview.platforms.android'],
    noarchive=False, optimize=0,
)
for destination, source, kind in a.binaries:
    if 'anaconda' in str(source).lower() or 'miniconda' in str(source).lower():
        raise RuntimeError(f'Forbidden host Conda binary source: {source}')
    if Path(destination).name.lower() in vc_names and Path(source).resolve().parent != system32.resolve():
        raise RuntimeError(f'MSVC runtime did not resolve to the pinned System32 family: {source}')
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='Inkshield',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(ROOT / 'assets/inkshield.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Inkshield')
