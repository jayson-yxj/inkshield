"""Run isolated frozen acceptance and terminate only this harness's EXE."""
from pathlib import Path
import subprocess,sys,time,json,hashlib
root=Path(__file__).resolve().parent
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
        subprocess.run([sys.executable,str(root/script),*args],cwd=root,check=True)
    record={'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'frozen_state':str(state),'identity':True,'plate_segments':True,'audio':True}
    (data/'acceptance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('FROZEN ACCEPTANCE PASS',json.dumps(record))
finally:
    if p.poll() is None:
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        p.wait(timeout=15)
