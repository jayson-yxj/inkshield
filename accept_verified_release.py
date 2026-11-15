"""Run all frozen acceptance gates serially, then create the release ZIP."""
from pathlib import Path
import subprocess
import sys
import uuid
from verify_sam_release_binding import ROOT, release_binding

if __name__ == '__main__':
    exe = ROOT/'dist/inkshield-20261110-r2/Inkshield/Inkshield.exe'
    release_binding(exe)
    stages = [
        ('bundle', ['verify_sam_bundle.py']),
        ('matrix', ['verify_sam_frozen_matrix.py', '--exe', str(exe), '--inference-slot']),
        ('legacy', ['verify_sam_legacy_release.py', '--exe', str(exe)]),
        ('desktop', ['verify_sam_desktop_launch.py', '--exe', str(exe), '--desktop-slot']),
        ('package', ['package_sam_release.py']),
    ]
    attempt = uuid.uuid4().hex[:8]
    for name, args in stages:
        print('START RELEASE STAGE '+name, flush=True)
        with (ROOT/('runtime/release-20261110-'+attempt+'-'+name+'.log')).open('x', encoding='utf-8') as log:
            subprocess.run([sys.executable, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        print('PASS RELEASE STAGE '+name, flush=True)
