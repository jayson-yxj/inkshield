"""Sequential frozen SAM acceptance with isolated, owned services.

Run with app .venv Python after the build and inference slot are assigned:
python verify_sam_frozen_matrix.py --exe PATH --source VIDEO --inference-slot
Runs CPU API, CUDA API, then full CUDA native acceptance. No source/model overrides.
"""
from __future__ import annotations

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))


import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from urllib.parse import urlparse

from verify_sam_packaged import ROOT, output_directory


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def port_open(url):
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=.5):
            return True
    except OSError:
        return False


def pid_running(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--source', '--input', dest='source', type=Path, default=Path.home() / 'Desktop' / '5.mp4')
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--x', type=float, default=646)
    parser.add_argument('--y', type=float, default=218)
    parser.add_argument('--reuse-api-evidence', type=Path, help='Reuse passed CPU/CUDA entries only when exact build and fixture binding match')
    parser.add_argument('--inference-slot', action='store_true')
    args = parser.parse_args()
    assert args.inference_slot, 'Exclusive CPU/GPU inference slot must be assigned first'
    exe, source, python = args.exe.resolve(strict=True), args.source.resolve(strict=True), args.python.resolve(strict=True)
    out = output_directory(args.output, 'sam-frozen-matrix')
    evidence = {'status': 'running', 'exe': str(exe), 'exe_sha256': digest(exe), 'source': str(source),
                'source_sha256': digest(source), 'python': str(python), 'runs': []}
    from verify_sam_release_binding import release_binding
    evidence['release_binding'] = release_binding(exe)
    reused = {}
    if args.reuse_api_evidence:
        prior = json.loads(args.reuse_api_evidence.read_text(encoding='utf-8'))
        assert prior['release_binding'] == evidence['release_binding'] and prior['source_sha256'] == evidence['source_sha256'] and prior['python'] == evidence['python'], 'Prior API evidence binding mismatch'
        for label in ('cpu-api', 'cuda-api'):
            entry = next(r for r in prior['runs'] if r['name'] == label)
            report_path = Path(entry['acceptance_evidence'])
            report = json.loads(report_path.read_text(encoding='utf-8'))
            assert entry['status'] == entry['acceptance_status'] == report['status'] == 'passed' and entry['test_exit_code'] == 0
            assert all(entry['cleanup'][key] for key in ('test_process_exited','launcher_process_exited','port_closed','service_pid_exited'))
            reused[label] = {**entry, 'reused_from': str(args.reuse_api_evidence.resolve()), 'reused_report_sha256': digest(report_path)}
    record_path = out / 'evidence.json'
    def save():
        record_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    try:
        for label, script, device in (('cpu-api', 'verify_sam_packaged.py', 'cpu'),
                                       ('cuda-api', 'verify_sam_packaged.py', 'cuda'),
                                       ('cuda-native', 'verify_sam_native_ui.py', 'cuda')):
            if label in reused:
                evidence['runs'].append(reused[label])
                save()
                print('REUSE VERIFIED ' + label, flush=True)
                continue
            run_dir = out / label
            run_dir.mkdir()
            data_dir = run_dir / 'data'
            data_dir.mkdir()
            state, process, test = None, None, None
            entry = {'name': label, 'status': 'starting', 'data_dir': str(data_dir), 'cleanup': {}}
            evidence['runs'].append(entry)
            save()
            env = os.environ.copy()
            # Frozen acceptance must resolve the shipped vendor/checkpoint by itself.
            for key in tuple(env):
                if key.startswith('INKSHIELD_SAM_') or key == 'INKSHIELD_DATA_DIR':
                    env.pop(key)
            env['OMP_NUM_THREADS'] = '4'
            env['MKL_NUM_THREADS'] = '4'
            with (run_dir / 'service.log').open('wb') as service_log, (run_dir / 'test.log').open('wb') as test_log:
                try:
                    process = subprocess.Popen([str(exe), '--serve-only', '--data-dir', str(data_dir)],
                                               cwd=str(exe.parent), env=env, stdout=service_log, stderr=subprocess.STDOUT)
                    entry['launcher_pid'] = process.pid
                    deadline = time.monotonic() + 180
                    state_path = None
                    while time.monotonic() < deadline:
                        candidates = list(data_dir.glob('desktop-*.json'))
                        if candidates:
                            state_path = candidates[0]
                            state = json.loads(state_path.read_text(encoding='utf-8'))
                            if port_open(state['url']):
                                break
                        if process.poll() is not None:
                            raise RuntimeError(f'Frozen service exited early: {process.returncode}; see service.log')
                        time.sleep(.2)
                    else:
                        raise TimeoutError('Frozen service did not publish a listening state within 180 seconds')
                    assert state['frozen'] is True, state
                    assert Path(state['data_dir']).resolve() == data_dir, state
                    entry['service'] = state
                    from verify_sam_bundle import verify_http
                    entry['http_assets'] = verify_http(state['url'], exe.parent)
                    command = [str(python), str(ROOT / 'tools/verification' / script), '--state', str(state_path), '--source', str(source),
                               '--x', str(args.x), '--y', str(args.y), '--device', device, '--require-frozen',
                               '--inference-slot', '--output', str(run_dir / 'acceptance')]
                    entry['command'] = command
                    entry['status'] = 'testing'
                    save()
                    print('START ' + label, flush=True)
                    test = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=test_log, stderr=subprocess.STDOUT)
                    entry['test_pid'] = test.pid
                    test.wait(timeout=1200)
                    entry['test_exit_code'] = test.returncode
                    report_path = run_dir / 'acceptance' / 'evidence.json'
                    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
                    entry['acceptance_evidence'] = str(report_path)
                    entry['acceptance_status'] = report.get('status')
                    assert test.returncode == 0 and report.get('status') == 'passed', f'{label} failed; see {run_dir / "test.log"}'
                    if label == 'cuda-native':
                        tutorial_out = run_dir / 'tutorial'
                        tutorial_command = [str(python), str(ROOT/'tests/ui/tutorial_v03_webview.py'), '--url', state['url'], '--source', str(exe.parent/'_internal/web/tutorial-preview.html'), '--output', str(tutorial_out)]
                        test = subprocess.Popen(tutorial_command, cwd=str(ROOT), env=env, stdout=test_log, stderr=subprocess.STDOUT)
                        test.wait(timeout=180)
                        assert test.returncode == 0, 'Frozen tutorial native dialog failed'
                        tutorial_report = json.loads((tutorial_out/'native-results.json').read_text(encoding='utf-8'))
                        assert tutorial_report.get('passed') == 36 and tutorial_report.get('source_unchanged') and all(c['ok'] for c in tutorial_report['checks']), tutorial_report
                        assert tutorial_report['source_sha256_after'] == evidence['release_binding']['assets']['tutorial-preview.html']
                        entry['tutorial_evidence'] = str(tutorial_out/'native-results.json')
                    entry['status'] = 'passed'
                    print('PASS ' + label, flush=True)
                finally:
                    # Only terminate the exact process trees this runner started.
                    for owned in (test, process):
                        if owned is not None and owned.poll() is None:
                            killed = subprocess.run(['taskkill', '/PID', str(owned.pid), '/T', '/F'],
                                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                                    errors='replace', timeout=30)
                            entry['cleanup'].setdefault('taskkill', []).append({'pid': owned.pid, 'exit_code': killed.returncode, 'output': killed.stdout})
                            owned.wait(timeout=30)
                    entry['cleanup']['test_process_exited'] = test is None or test.poll() is not None
                    entry['cleanup']['launcher_process_exited'] = process is None or process.poll() is not None
                    if state:
                        deadline = time.monotonic() + 10
                        while port_open(state['url']) and time.monotonic() < deadline:
                            time.sleep(.2)
                        entry['cleanup']['port_closed'] = not port_open(state['url'])
                        entry['cleanup']['service_pid_exited'] = not pid_running(int(state['pid']))
                        assert entry['cleanup']['port_closed'], 'Owned service port still listening after cleanup'
                        assert entry['cleanup']['service_pid_exited'], 'Owned frozen service PID still running after cleanup'
                    save()
        evidence['status'] = 'passed'
    except BaseException:
        evidence['status'] = 'failed'
        evidence['error'] = traceback.format_exc()
        raise
    finally:
        save()
        print('Matrix evidence: ' + str(record_path), flush=True)


if __name__ == '__main__':
    main()
