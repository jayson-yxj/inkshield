"""Run the segment editor Node interaction regression suite without changing files."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import shutil
import subprocess

if __name__ == '__main__':
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required to run verify_segments_ui.js')
    raise SystemExit(subprocess.call([node, str(Path(__file__).with_suffix('.js'))]))
