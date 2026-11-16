"""Verify release source assets and model/resource inventory in onedir."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import hashlib, json, urllib.request

FRONTEND_ROUTES={'/':'index.html','/tutorial':'tutorial-preview.html', '/startup':'splash-preview.html',
                 '/layers_ui.js':'layers_ui.js','/workspace_ui.js':'workspace_ui.js','/workspace_ui.css':'workspace_ui.css'}

def verify_http(url, folder):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    results={}
    for route, name in FRONTEND_ROUTES.items():
        with opener.open(url.rstrip('/')+route, timeout=30) as response:
            assert response.status==200, route
            actual=hashlib.sha256(response.read()).hexdigest()
            expected=digest(folder/'_internal'/'web'/name)
            assert actual==expected==digest(ROOT/'src/inkshield/web'/name), 'HTTP/bundle/source mismatch '+name
            results[route]={'sha256':actual,'status':response.status}
    return results

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'dist/inkshield-20261110-r2/Inkshield'
INTERNAL=FOLDER/'_internal'

def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    matches={}
    for name in ['index.html','layers_ui.js','workspace_ui.js','workspace_ui.css','tutorial-preview.html','splash-preview.html','docs/distribution/SAM_PACKAGING.md','models/det_500m.onnx','models/w600k_mbf.onnx','models/y5fu_320x_sim.onnx','models/sam2.1_hiera_tiny.pt','models/SAM21_SOURCE.md','models/SAM21_PROVENANCE.json','models/SAM21_LICENSE.txt']:
        original=ROOT/name
        frozen=INTERNAL/name
        if name in FRONTEND_ROUTES.values():
            original=ROOT/'src/inkshield/web'/name
            frozen=INTERNAL/'web'/name
        if not frozen.is_file(): raise AssertionError('Missing bundled asset '+name)
        expected=digest(original)
        if digest(frozen)!=expected: raise AssertionError('Bundled source mismatch '+name)
        matches[name]=expected
    required=['vendor/sam2/sam2/build_sam.py','vendor/sam2/sam2/configs/sam2.1/sam2.1_hiera_t.yaml']
    for name in required:
        if not (INTERNAL/name).is_file(): raise AssertionError('Missing vendor resource '+name)
    onnx=sorted(p.name for p in INTERNAL.rglob('*.onnx'))
    if onnx!=sorted(['det_500m.onnx','w600k_mbf.onnx','y5fu_320x_sim.onnx']): raise AssertionError('Unexpected ONNX inventory '+str(onnx))
    prohibited=[str(p.relative_to(FOLDER)) for p in FOLDER.rglob('*') if p.is_file() and p.suffix.lower() in {'.mp4','.avi','.mov','.npy','.npz'}]
    if prohibited: raise AssertionError('User/research media in release '+str(prohibited))
    cuda=[p.name for p in INTERNAL.rglob('*.dll') if p.name.lower().startswith(('cudart','cublas','cudnn'))]
    if not cuda: raise AssertionError('CUDA runtime DLLs missing')
    import imageio_ffmpeg
    source_ff=Path(imageio_ffmpeg.get_ffmpeg_exe())
    frozen_ff=INTERNAL/'imageio_ffmpeg/binaries'/source_ff.name
    assert frozen_ff.is_file() and digest(frozen_ff)==digest(source_ff), 'Wheel FFmpeg missing or hash differs'
    record={'ffmpeg_binary':{'path':str(frozen_ff),'sha256':digest(frozen_ff)},'source_assets':matches,'onnx_models':onnx,'cuda_dlls':cuda,'source_vendor_resources':required,'user_media':prohibited}
    (ROOT/'runtime/sam-bundle-verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SAM BUNDLE PASS',json.dumps(record,ensure_ascii=False))

if __name__=='__main__': main()
