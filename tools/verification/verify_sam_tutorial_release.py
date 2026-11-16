"""Verify bundled tutorial independently without OS input or foreground requests."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from pathlib import Path
import json, os, subprocess, sys, time, traceback, uuid
from verify_sam_release_binding import ROOT, release_binding
from verify_sam_frozen_matrix import pid_running, port_open
from verify_sam_bundle import verify_http

def main():
    exe=ROOT/'dist/inkshield-20261110-r2/Inkshield/Inkshield.exe'
    binding=release_binding(exe)
    out=ROOT/'runtime'/('sam-tutorial-'+uuid.uuid4().hex[:10]); out.mkdir()
    data=out/'data'; data.mkdir()
    record={'status':'running','release_binding':binding,'cleanup':{}}
    process=test=None; state=None
    env=os.environ.copy()
    for key in tuple(env):
        if key.startswith('INKSHIELD_SAM_') or key=='INKSHIELD_DATA_DIR': env.pop(key)
    try:
        with (out/'service.log').open('wb') as log:
            process=subprocess.Popen([str(exe),'--serve-only','--data-dir',str(data)],cwd=exe.parent,env=env,stdout=log,stderr=subprocess.STDOUT)
            record['launcher_pid']=process.pid
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                for p in data.glob('desktop-*.json'):
                    state=json.loads(p.read_text(encoding='utf-8'))
                    if port_open(state['url']): break
                if state and port_open(state['url']): break
                if process.poll() is not None: raise RuntimeError('Frozen tutorial service exited early')
                time.sleep(.2)
            assert state and state['frozen'] and Path(state['data_dir']).resolve()==data.resolve()
            record['service']=state
            record['http_assets']=verify_http(state['url'],exe.parent)
            command=[sys.executable,str(ROOT/'tests/ui/tutorial_v03_webview.py'),'--url',state['url'],'--source',str(exe.parent/'_internal/web/tutorial-preview.html'),'--output',str(out/'tutorial')]
            with (out/'tutorial.log').open('wb') as testlog:
                test=subprocess.Popen(command,cwd=ROOT,env=env,stdout=testlog,stderr=subprocess.STDOUT)
                record['test_pid']=test.pid
                test.wait(timeout=180)
            report_path=out/'tutorial/native-results.json'
            report=json.loads(report_path.read_text(encoding='utf-8'))
            assert test.returncode==0 and report.get('passed')==36 and report.get('source_unchanged') and all(c['ok'] for c in report['checks']), report
            assert report['source_sha256_after']==binding['assets']['tutorial-preview.html']
            assert release_binding(exe)==binding
            record.update(status='passed',tutorial_evidence=str(report_path),passed=report['passed'])
    except BaseException:
        record.update(status='failed',error=traceback.format_exc())
        raise
    finally:
        for owned in (test,process):
            if owned is not None and owned.poll() is None:
                subprocess.run(['taskkill','/PID',str(owned.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
                owned.wait(timeout=30)
        record['cleanup'].update(test_process_exited=test is None or test.poll() is not None,launcher_process_exited=process is None or process.poll() is not None)
        if state:
            deadline=time.monotonic()+10
            while port_open(state['url']) and time.monotonic()<deadline: time.sleep(.2)
            record['cleanup'].update(port_closed=not port_open(state['url']),service_pid_exited=not pid_running(int(state['pid'])))
        if not all(record['cleanup'].values()): record['status']='failed'
        (out/'evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(str(out/'evidence.json'),flush=True)
        assert all(record['cleanup'].values()),record['cleanup']
if __name__=='__main__': main()
