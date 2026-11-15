"""Bind acceptance evidence to the reviewed source freeze and exact bundle assets."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
FREEZE = ROOT / 'runtime/release-20261110-source-freeze.json'
ASSETS = ('index.html', 'layers_ui.js', 'workspace_ui.js', 'workspace_ui.css', 'tutorial-preview.html', 'splash-preview.html')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_source_freeze():
    frozen = json.loads(FREEZE.read_text(encoding='utf-8'))
    required = {'index.html', 'layers_ui.js', 'workspace_ui.js', 'workspace_ui.css', 'server.py', 'desktop.py', 'mask_layers.py', 'mask_timeline.py', 'preview_video.py', 'sam_service.py', 'sam_engine.py', 'tutorial-preview.html'}
    if not required.issubset(frozen):
        raise RuntimeError('Source freeze incomplete: '+str(sorted(required-set(frozen))))
    for name, expected in frozen.items():
        if digest(ROOT/name) != expected:
            raise RuntimeError('Reviewed source changed: '+name)
    return frozen


def record_build(exe, frozen):
    exe = Path(exe).resolve()
    if verify_source_freeze() != frozen:
        raise RuntimeError('Source freeze changed during build')
    assets = {name:digest(exe.parent/'_internal'/name) for name in ASSETS}
    if any(assets[name] != digest(ROOT/name) for name in ASSETS):
        raise RuntimeError('Built assets differ from source')
    record = {'source_freeze':frozen, 'exe_sha256':digest(exe), 'assets':assets}
    with (exe.parent/'BUILD_PROVENANCE.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    return record


def release_binding(exe):
    exe = Path(exe).resolve()
    frozen = verify_source_freeze()
    assets = {}
    for name in ASSETS:
        actual = digest(exe.parent/'_internal'/name)
        if actual != digest(ROOT/name):
            raise RuntimeError('Bundle asset differs from reviewed source: '+name)
        assets[name] = actual
    provenance = json.loads((exe.parent/'BUILD_PROVENANCE.json').read_text(encoding='utf-8'))
    if provenance['source_freeze'] != frozen or provenance['exe_sha256'] != digest(exe) or provenance['assets'] != assets:
        raise RuntimeError('Build provenance differs from current freeze or bundle')
    return {'exe':str(exe), 'exe_sha256':digest(exe), 'source_freeze':frozen, 'assets':assets,
            'build_provenance_sha256':digest(exe.parent/'BUILD_PROVENANCE.json')}
