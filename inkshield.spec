# -*- mode: python ; coding: utf-8 -*-
"""Windows x64, windowed, one-file build. Run with the existing project venv."""
from pathlib import Path
from importlib import metadata
import platform
import os
import struct
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata, collect_all

ROOT = Path(SPECPATH).resolve()
if sys.platform != 'win32' or struct.calcsize('P') != 8 or platform.machine().lower() not in ('amd64', 'x86_64'):
    raise RuntimeError('Inkshield must be built using native Windows x64 Python.')

# Deliberately enumerate assets: no runtime uploads, research, tests, or unused models.
asset_names = [
    'index.html',
    'splash-preview.html',
    'tutorial-preview.html',
    'assets/inkshield.ico',
    'models/det_500m.onnx',
    'models/w600k_mbf.onnx',
    'models/FACE_SOURCE.md',
    'models/INSIGHTFACE_LICENSE.txt',
    'models/y5fu_320x_sim.onnx',
    'models/SOURCE.md',
    'models/HYPERLPR_SOURCE.md',
    'PACKAGING_REPORT.md',
    'PACKAGING_DEPENDENCIES.json',
    'requirements-packaging.lock.txt',
    'AUDIO_DEPENDENCIES.md',
]
datas = []
for name in asset_names:
    source = ROOT / name
    if not source.is_file():
        raise FileNotFoundError(source)
    datas.append((str(source), str(Path(name).parent)))

# Preserve installed distribution license/notice files verbatim, including bundled
# OpenCV/FFmpeg and NumPy notices. Inventory may include build-only distributions.
for dist in metadata.distributions():
    label = dist.metadata.get('Name', 'unknown').replace('/', '_').replace('\\', '_')
    for item in dist.files or []:
        leaf = Path(str(item)).name.lower()
        parts = [part.lower() for part in Path(str(item)).parts]
        if (leaf.startswith(('license', 'licence', 'copying', 'notice', 'third_party_notices'))
                or 'licenses' in parts) and not leaf.endswith(('.py', '.pyc', '.pyd', '.dll')):
            source = Path(dist.locate_file(item))
            if source.is_file():
                relative_parent = Path(str(item)).parent
                if '..' not in relative_parent.parts:
                    datas.append((str(source), str(Path('third_party_licenses') / label / relative_parent)))

python_license = Path(sys.base_prefix) / 'LICENSE.txt'
if python_license.is_file():
    datas.append((str(python_license), 'third_party_licenses/CPython'))

for package in ('onnxruntime', 'fastapi', 'uvicorn', 'pywebview', 'pythonnet', 'clr_loader'):
    datas += copy_metadata(package)

# Package hooks handle NumPy, cv2, tkinter, webview/lib, Python.Runtime.dll,
# clr_loader/ffi/dlls and _cffi_backend. Explicit collection ensures CPU ORT and
# OpenCV's FFmpeg video codec DLL are retained; PyInstaller deduplicates entries.
# Do not let a globally installed Anaconda supply obsolete VC++ DLLs through
# PATH. ORT 1.23.2 cannot initialize against Anaconda's 14.27 runtime here.
system32 = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32'
vc_names = ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll',
            'msvcp140_1.dll', 'msvcp140_2.dll', 'concrt140.dll')
for name in vc_names:
    if not (system32 / name).is_file():
        raise FileNotFoundError(f'Install the current Microsoft VC++ x64 Redistributable before building: {name}')
binaries = [(str(system32 / name), '.') for name in vc_names]
binaries += collect_dynamic_libs('onnxruntime') + collect_dynamic_libs('cv2')
os.environ['PATH'] = os.pathsep.join((str(Path(sys.executable).parent),
    str(Path(sys.base_prefix)), str(system32), str(system32.parent)))
hiddenimports = [
    'server', 'app_paths', 'cpu_runtime', 'masking', 'plate_detector',
    'face_detector', 'identity_gallery', 'scrfd',
    'uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
    'uvicorn.lifespan.on', 'uvicorn.lifespan.off', 'python_multipart',
    'webview.platforms.winforms', 'webview.platforms.edgechromium',
    'pythonnet', 'clr', 'clr_loader', '_cffi_backend',
]
# PyAV uses wheel-vendored shared FFmpeg DLLs (av.libs), never the GPL
# imageio-ffmpeg executable used only by development regression fixtures.
av_datas, av_binaries, av_hidden = collect_all('av')
datas += av_datas + copy_metadata('av')
binaries += av_binaries
av_dist = metadata.distribution('av')
for item in av_dist.files or []:
    if str(item).replace('\\', '/').startswith('av.libs/') and str(item).lower().endswith('.dll'):
        binaries.append((str(av_dist.locate_file(item)), 'av.libs'))
hiddenimports += av_hidden

a = Analysis(
    [str(ROOT / 'desktop.py')], pathex=[str(ROOT)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['pytest', 'IPython', 'notebook', 'matplotlib',
                                'torch', 'tensorflow', 'mediapipe', 'research', 'imageio_ffmpeg',
                                'webview.platforms.qt', 'webview.platforms.gtk',
                                'webview.platforms.cocoa', 'webview.platforms.android'],
    noarchive=False, optimize=0,
)
# Fail closed if binary dependency analysis ever reintroduces host Conda DLLs.
for destination, source, kind in a.binaries:
    if 'anaconda' in str(source).lower() or 'miniconda' in str(source).lower():
        raise RuntimeError(f'Forbidden host Conda binary source: {source}')
    if Path(destination).name.lower() in vc_names and Path(source).resolve().parent != system32.resolve():
        raise RuntimeError(f'MSVC runtime did not resolve to the pinned System32 family: {source}')
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='Inkshield',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(ROOT / 'assets/inkshield.ico'),
)
