"""Smoke-test the actual packaged desktop host without model inference.

Only run after the parent assigns a desktop slot:
python verify_sam_desktop_launch.py --exe PATH --desktop-slot
The executable opens its normal GUI; no external pywebview host is used.
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
import json
from pathlib import Path
import subprocess
import time
import traceback
import urllib.request

from verify_sam_frozen_matrix import digest, pid_running, port_open
from verify_sam_packaged import output_directory


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]


def processes():
    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError()
    rows = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            rows[int(entry.th32ProcessID)] = {'pid': int(entry.th32ProcessID),
                'parent_pid': int(entry.th32ParentProcessID), 'exe': entry.szExeFile}
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return rows


def descendants(rows, root):
    owned = {root}
    while True:
        expanded = owned | {pid for pid, row in rows.items() if row['parent_pid'] in owned}
        if expanded == owned:
            return owned
        owned = expanded


def windows(owned):
    user = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.PostMessageW.restype = wintypes.BOOL
    result = []

    def describe(hwnd):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in owned:
            return None
        title, cls = ctypes.create_unicode_buffer(1024), ctypes.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, len(title))
        user.GetClassNameW(hwnd, cls, len(cls))
        return {'hwnd': int(hwnd), 'pid': pid.value, 'title': title.value,
                'class': cls.value, 'visible': bool(user.IsWindowVisible(hwnd))}

    @callback_type
    def top(hwnd, unused):
        row = describe(hwnd)
        if row is not None:
            row['children'] = []

            @callback_type
            def child(child_hwnd, unused):
                child_row = describe(child_hwnd)
                if child_row is not None:
                    row['children'].append(child_row)
                return True

            user.EnumChildWindows(hwnd, child, 0)
            result.append(row)
        return True

    user.EnumWindows(top, 0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--desktop-slot', action='store_true')
    args = parser.parse_args()
    assert args.desktop_slot, 'Parent must assign the desktop slot before actual GUI launch'
    exe = args.exe.resolve(strict=True)
    out = output_directory(args.output, 'sam-desktop-launch')
    data = out / 'data'
    data.mkdir()
    evidence = {'status': 'running', 'exe': str(exe), 'exe_sha256': digest(exe),
                'data_dir': str(data), 'inference_requested': False, 'cleanup': {}}
    from verify_sam_release_binding import release_binding
    evidence['release_binding'] = release_binding(exe)
    process, state, hwnd = None, None, None
    observed_pids = set()
    record = out / 'evidence.json'

    def save():
        record.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')

    try:
        import os
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith('INKSHIELD_SAM_') or key == 'INKSHIELD_DATA_DIR':
                env.pop(key)
        with (out / 'launcher.log').open('wb') as log:
            process = subprocess.Popen([str(exe), '--data-dir', str(data)], cwd=str(exe.parent),
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
            evidence['launcher_pid'] = process.pid
            save()
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Packaged desktop exited before renderer readiness')
                rows = processes()
                owned = descendants(rows, process.pid)
                observed_pids.update(owned)
                if state is None:
                    for candidate in data.glob('desktop-*.json'):
                        try:
                            candidate_state = json.loads(candidate.read_text(encoding='utf-8'))
                        except json.JSONDecodeError:
                            continue
                        assert int(candidate_state['pid']) in owned, 'State PID not owned by launcher'
                        assert candidate_state['frozen'] is True, candidate_state
                        assert Path(candidate_state['data_dir']).resolve() == data, candidate_state
                        state = candidate_state
                        evidence['service'] = state
                        break
                owned_windows = windows(owned)
                for window in owned_windows:
                    renderer_children = [child for child in window['children']
                                         if child['class'].startswith(('Chrome_', 'WebView'))]
                    renderer_processes = [row for pid, row in rows.items()
                                          if pid in owned and row['exe'].lower() == 'msedgewebview2.exe']
                    if (window['visible'] and window['title'].startswith('隐映 · 本地视频隐私工作台')
                            and renderer_children and renderer_processes and state and port_open(state['url'])):
                        hwnd = window['hwnd']
                        evidence['window'] = window
                        evidence['renderer_processes'] = renderer_processes
                        break
                if hwnd:
                    break
                time.sleep(.2)
            else:
                raise TimeoutError('Actual packaged desktop WebView2 HWND/process did not become ready')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(state['url'] + 'startup', timeout=30) as response:
                assert response.status == 200
                evidence['startup_http_status'] = response.status
            with opener.open(state['url'] + 'api/sam/capabilities', timeout=120) as response:
                capabilities = json.load(response)
            assert capabilities['available'] is True, capabilities
            assert capabilities['default_device'] in ('cpu', 'cuda'), capabilities
            assert any(d['id'] == 'cpu' and d['available'] for d in capabilities['devices']), capabilities
            evidence['capabilities'] = capabilities
            deadline = time.monotonic() + 180
            while True:
                with opener.open(state['url'] + 'api/sam/warmup', timeout=30) as response:
                    warmup = json.load(response)
                assert warmup['state'] != 'error', warmup
                if warmup['state'] == 'ready': break
                assert time.monotonic() < deadline, warmup
                time.sleep(.2)
            gpu = any(d['id']=='cuda' and d['available'] for d in capabilities['devices'])
            assert warmup['device'] == ('cuda' if gpu else 'cpu') or (warmup['device']=='cpu' and warmup.get('fallback_reason')), warmup
            with opener.open(state['url'] + 'api/sam/capabilities', timeout=30) as response:
                ready_capabilities = json.load(response)
            assert ready_capabilities['default_device'] == warmup['device'], (ready_capabilities, warmup)
            evidence['warmup'] = warmup
            from verify_sam_bundle import verify_http
            evidence['http_assets'] = verify_http(state['url'], exe.parent)
            # Revalidate current HWND ownership immediately before sending WM_CLOSE.
            owned = descendants(processes(), process.pid)
            current = next((w for w in windows(owned) if w['hwnd'] == hwnd
                            and w['title'].startswith('隐映 · 本地视频隐私工作台')), None)
            assert current is not None, 'Owned desktop window disappeared before WM_CLOSE'
            assert ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0), 'WM_CLOSE failed'
            evidence['close'] = {'hwnd': hwnd, 'pid': current['pid'], 'message': 'WM_CLOSE'}
            process.wait(timeout=45)
            assert process.returncode == 0, process.returncode
            deadline = time.monotonic() + 15
            while (port_open(state['url']) or pid_running(int(state['pid']))
                   or any(pid_running(pid) for pid in observed_pids)) and time.monotonic() < deadline:
                time.sleep(.2)
            evidence['cleanup'] = {'launcher_exited': process.poll() is not None,
                'service_pid_exited': not pid_running(int(state['pid'])),
                'port_closed': not port_open(state['url']),
                'observed_owned_pids_exited': all(not pid_running(pid) for pid in observed_pids)}
            assert all(evidence['cleanup'].values()), evidence['cleanup']
            evidence['status'] = 'passed'
    except BaseException:
        evidence['status'] = 'failed'
        evidence['error'] = traceback.format_exc()
        raise
    finally:
        if process is not None and process.poll() is None:
            killed = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            evidence['failure_cleanup_taskkill_exit_code'] = killed.returncode
            process.wait(timeout=30)
        save()
        print('Desktop launch evidence: ' + str(record), flush=True)


if __name__ == '__main__':
    main()
