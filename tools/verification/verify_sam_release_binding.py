"""Bind acceptance evidence to the reviewed source freeze and exact bundle assets."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
# Historical manifests remain read-only; the reorganized tree needs a new review.
FREEZE = ROOT / 'runtime/release-source-freeze.json'
WEB_ROOT = ROOT / 'src/inkshield/web'
ASSETS = ('index.html', 'layers_ui.js', 'workspace_ui.js', 'workspace_ui.css', 'tutorial-preview.html', 'splash-preview.html')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_source_freeze():
    if not FREEZE.is_file():
        raise RuntimeError('Release freeze must be regenerated and reviewed for the src/inkshield layout; historical release-20261110-source-freeze.json is not reusable.')
    frozen = json.loads(FREEZE.read_text(encoding='utf-8'))
    required = {'src/inkshield/web/' + name for name in ASSETS}
    required.update('src/inkshield/' + name + '.py' for name in ('server', 'desktop', 'mask_layers', 'mask_timeline', 'preview_video', 'sam_service', 'sam_engine'))
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
    assets = {name:digest(exe.parent/'_internal'/'web'/name) for name in ASSETS}
    if any(assets[name] != digest(WEB_ROOT/name) for name in ASSETS):
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
        actual = digest(exe.parent/'_internal'/'web'/name)
        if actual != digest(WEB_ROOT/name):
            raise RuntimeError('Bundle asset differs from reviewed source: '+name)
        assets[name] = actual
    provenance = json.loads((exe.parent/'BUILD_PROVENANCE.json').read_text(encoding='utf-8'))
    if provenance['source_freeze'] != frozen or provenance['exe_sha256'] != digest(exe) or provenance['assets'] != assets:
        raise RuntimeError('Build provenance differs from current freeze or bundle')
    return {'exe':str(exe), 'exe_sha256':digest(exe), 'source_freeze':frozen, 'assets':assets,
            'build_provenance_sha256':digest(exe.parent/'BUILD_PROVENANCE.json')}
