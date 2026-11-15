"""Build only the frozen reviewed release and attest source/assets before acceptance."""
from pathlib import Path
import subprocess
import os
from verify_sam_release_binding import ROOT, verify_source_freeze, record_build

if __name__ == '__main__':
    frozen = verify_source_freeze()
    shell = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    with (ROOT/'runtime/release-20261110-r2-pyinstaller.log').open('x', encoding='utf-8') as log:
        subprocess.run([str(shell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'build_sam_exe.ps1')], cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT)
    record_build(ROOT/'dist/inkshield-20261110-r2/Inkshield/Inkshield.exe', frozen)
    print('BUILD AND SOURCE PROVENANCE PASS', flush=True)
