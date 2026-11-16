"""Split the verified portable ZIP for GitHub's 2 GiB asset limit."""

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
SOURCE = ROOT / 'dist/inkshield-20261110-r2/隐映-Windows-x64-多层工作区CPU-GPU版-20261110-修订2.zip'
OUTPUT = ROOT / 'dist/github-release-20261110-r2'
EXPECTED = 'f7cc17d4a61400fe1cd0daa72ccc7d0916d5c35df79635ecc7f5f5e1c46b1335'

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    records = []
    with SOURCE.open('rb') as source:
        for number in range(1, 3):
            target = OUTPUT / f'Inkshield-Windows-x64-r2.zip.part{number}'
            part_digest = hashlib.sha256()
            remaining = 1500 * 1024 * 1024
            with target.open('wb') as output:
                while remaining:
                    data = source.read(min(8 * 1024 * 1024, remaining))
                    if not data:
                        break
                    output.write(data)
                    digest.update(data)
                    part_digest.update(data)
                    remaining -= len(data)
            records.append({'name': target.name, 'bytes': target.stat().st_size, 'sha256': part_digest.hexdigest()})
        if source.read(1):
            raise RuntimeError('Archive needs more than two volumes')
    if digest.hexdigest() != EXPECTED:
        raise RuntimeError('Original release ZIP hash mismatch')
    record = {'archive': 'Inkshield-Windows-x64-r2.zip', 'sha256': EXPECTED, 'parts': records}
    (OUTPUT / 'SHA256.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    script = '''@echo off\r\ncd /d "%~dp0"\r\ncopy /b Inkshield-Windows-x64-r2.zip.part1+Inkshield-Windows-x64-r2.zip.part2 Inkshield-Windows-x64-r2.zip\r\nif errorlevel 1 goto failed\r\npowershell -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 -LiteralPath 'Inkshield-Windows-x64-r2.zip').Hash -ne 'EXPECTED') { Write-Error 'SHA256 mismatch'; exit 1 }"\r\nif errorlevel 1 goto failed\r\necho Verified. Extract Inkshield-Windows-x64-r2.zip completely, then launch Inkshield.exe.\r\npause\r\nexit /b 0\r\n:failed\r\necho Failed. Download both parts into the same folder and retry.\r\npause\r\nexit /b 1\r\n'''.replace('EXPECTED', EXPECTED)
    (OUTPUT / 'Merge-and-verify.cmd').write_bytes(script.encode('ascii'))
    print(json.dumps(record, indent=2))

if __name__ == '__main__':
    main()
