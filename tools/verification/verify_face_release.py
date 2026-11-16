"""Run isolated frozen acceptance and terminate only this harness's EXE."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import subprocess,sys,time,json,hashlib
root=Path(__file__).resolve().parents[2]
data=root/'runtime/timeline-release-acceptance';data.mkdir(parents=True,exist_ok=True)
exe=root/'dist/timeline-editing-trial/Inkshield.exe'
p=subprocess.Popen([str(exe),'--serve-only','--data-dir',str(data)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    deadline=time.monotonic()+90
    state=None
    while time.monotonic()<deadline:
        assert p.poll() is None, 'Frozen process exited before ready'
        candidates=list(data.glob('desktop-*.json'))
        for f in candidates:
            info=json.loads(f.read_text(encoding='utf-8'))
            if info['pid']==p.pid or info['frozen'] and f.stat().st_mtime>time.time()-90:
                state=f;break
        if state:break
        time.sleep(.2)
    assert state,'Frozen state missing'
    for script,args in [('verify_identity_packaged.py',[str(state),'--input',str(root/'runtime/identity-source-verification/face-identity-short.mp4'),'--require-frozen','--output','runtime/timeline-frozen-verification']),('verify_packaged.py',[str(state),'--require-frozen']),('runtime/verify_frozen_audio.py',[str(state)])]:
        subprocess.run([sys.executable,str(root/('tools/verification/'+script if script.startswith('verify_') else script)),*args],cwd=root,check=True)
    record={'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'frozen_state':str(state),'identity':True,'plate_segments':True,'audio':True}
    (data/'acceptance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('FROZEN ACCEPTANCE PASS',json.dumps(record))
finally:
    if p.poll() is None:
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        p.wait(timeout=15)
