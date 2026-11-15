"""Existing face/plate/audio acceptance against the new SAM application."""
from pathlib import Path
import argparse, subprocess, sys, time, json, hashlib, uuid
from verify_sam_frozen_matrix import pid_running, port_open


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    exe=args.exe.resolve()
    from verify_sam_release_binding import release_binding
    binding=release_binding(exe)
    data=root/'runtime'/('sam-legacy-'+uuid.uuid4().hex[:10])
    data.mkdir(parents=True)
    process=subprocess.Popen([str(exe),'--serve-only','--data-dir',str(data)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    state=None
    info=None
    try:
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if process.poll() is not None:
                raise RuntimeError('Frozen process exited before ready')
            for candidate in data.glob('desktop-*.json'):
                info=json.loads(candidate.read_text(encoding='utf-8'))
                if info.get('frozen'):
                    state=candidate
                    break
            if state: break
            time.sleep(.2)
        if not state: raise RuntimeError('Frozen state missing')
        output=data/'identity'
        tasks=[('verify_identity_packaged.py',[str(state),'--input',str(root/'runtime/identity-source-verification/face-identity-short.mp4'),'--require-frozen','--expected-targets','face','plate','custom','--output',str(output)]),('verify_packaged.py',[str(state),'--require-frozen']),('runtime/verify_frozen_audio.py',[str(state)])]
        for script, arguments in tasks:
            subprocess.run([sys.executable,str(root/script),*arguments],cwd=root,check=True)
        with exe.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        record={'exe':str(exe),'exe_sha256':digest,'release_binding':binding,'state':str(state),'identity':True,'plate_segments':True,'audio':True}
        (data/'acceptance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        print('LEGACY FROZEN ACCEPTANCE PASS', json.dumps(record))
    finally:
        if process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            process.wait(timeout=15)
        cleanup={'launcher_exited':process.poll() is not None}
        if state is not None and info is not None:
            deadline=time.monotonic()+10
            while port_open(info['url']) and time.monotonic()<deadline:
                time.sleep(.2)
            cleanup.update(service_pid_exited=not pid_running(int(info['pid'])),port_closed=not port_open(info['url']))
            (data/'cleanup.json').write_text(json.dumps(cleanup,indent=2),encoding='utf-8')
            assert all(cleanup.values()),cleanup

if __name__=='__main__': main()
