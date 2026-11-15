"""Run the segment editor Node interaction regression suite without changing files."""
from pathlib import Path
import shutil
import subprocess

if __name__ == '__main__':
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required to run verify_segments_ui.js')
    raise SystemExit(subprocess.call([node, str(Path(__file__).with_suffix('.js'))]))
