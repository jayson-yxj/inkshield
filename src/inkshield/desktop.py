"""Offline Windows launcher. Closing the desktop window stops its local server."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description='Inkshield local video privacy editor')
    parser.add_argument('--serve-only', action='store_true', help='Run packaged service without opening a window (diagnostics)')
    parser.add_argument('--port', type=int, default=0, help='Loopback port; default chooses an available port')
    parser.add_argument('--data-dir', help='Override persistent data folder')
    args = parser.parse_args()
    if args.data_dir:
        os.environ['INKSHIELD_DATA_DIR'] = str(Path(args.data_dir).resolve())
    from .app_paths import DATA_ROOT, RESOURCE_ROOT
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = DATA_ROOT / 'inkshield.log'
    # Windowed PyInstaller has no stdout/stderr. Give libraries valid streams.
    stream = open(log_path, 'a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(stream)],
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s', force=True)
    logger = logging.getLogger('inkshield.desktop')
    state_file = DATA_ROOT / f'desktop-{os.getpid()}.json'
    sock = None
    service = None
    thread = None
    try:
        import uvicorn
        from .server import app
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Bind once and hand the same socket to Uvicorn: no free-port race.
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(('127.0.0.1', args.port))
        sock.listen(128)
        url = f'http://127.0.0.1:{sock.getsockname()[1]}/'
        config = uvicorn.Config(app, host='127.0.0.1', log_config=None, access_log=False,
                                loop='asyncio', http='h11', ws='none')
        service = uvicorn.Server(config)
        thread = threading.Thread(target=service.run, kwargs={'sockets': [sock]}, name='local-server', daemon=True)
        thread.start()
        deadline = time.monotonic() + 40
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while not service.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('本地服务启动失败，请查看运行日志。')
            time.sleep(.05)
        with opener.open(url, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError('本地界面未能加载。')
        state_file.write_text(json.dumps({'pid': os.getpid(), 'url': url, 'data_dir': str(DATA_ROOT),
                                         'frozen': bool(getattr(sys, 'frozen', False))}), encoding='utf-8')
        logger.info('Ready at %s; data=%s', url, DATA_ROOT)
        try:
            # The service owns the singleton, lock and background worker. Start
            # only after HTTP is ready; optional SAM failures never block the UI.
            from .sam_service import start_warmup
            start_warmup()
        except Exception:
            logger.exception('Optional SAM warmup could not start; base service remains available')
        if args.serve_only:
            while thread.is_alive():
                thread.join(timeout=.5)
        else:
            try:
                import webview
                # pywebview otherwise silently falls back to the obsolete MSHTML.
                from webview.platforms.winforms import renderer
                if renderer != 'edgechromium':
                    raise RuntimeError('未检测到可用的 WebView2，将使用浏览器模式。')
                webview.settings['ALLOW_DOWNLOADS'] = True
                window = webview.create_window('隐映 · 本地视频隐私工作台', url + 'startup', width=1440, height=900,
                                               min_size=(960, 640), background_color='#101114')
                def confirm_close():
                    # Do not terminate in-progress output without an explicit choice.
                    from .server import JOB_LOCK, JOBS
                    with JOB_LOCK:
                        busy = any(j.get('state') in ('queued', 'loading', 'analyzing', 'processing') for j in JOBS.values())
                    if busy:
                        return window.create_confirmation_dialog('任务正在运行', '关闭窗口会停止当前分析或导出，确定关闭？')
                    return True
                window.events.closing += confirm_close
                loaded, closed, failed = threading.Event(), threading.Event(), threading.Event()
                window.events.loaded += lambda: loaded.set()
                window.events.closed += lambda: closed.set()
                def watch_renderer():
                    # Some WebView2 initialization failures are reported only by
                    # an async callback, not raised out of webview.start().
                    deadline = time.monotonic() + 45
                    while not loaded.is_set() and not closed.wait(.25):
                        if time.monotonic() > deadline:
                            failed.set()
                            window.destroy()
                            return
                threading.Thread(target=watch_renderer, daemon=True, name='renderer-watchdog').start()
                webview.start(gui='edgechromium', storage_path=str(DATA_ROOT / 'webview'), private_mode=False,
                              icon=str(RESOURCE_ROOT / 'assets' / 'inkshield.ico'))
                if failed.is_set():
                    raise RuntimeError('WebView2 未能载入界面，将使用浏览器模式。')
            except Exception:
                logger.exception('Embedded window unavailable; opening browser fallback')
                browser_fallback(url + 'startup', DATA_ROOT)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.exception('Startup failed')
        if not args.serve_only:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, f'{exc}\n\n运行日志：{log_path}', '隐映启动失败', 0x10)
            except Exception:
                pass
        return 1
    finally:
        if service is not None:
            service.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
        if sock is not None:
            sock.close()
        if state_file.exists():
            state_file.unlink()
    return 0


def browser_fallback(url, data_root):
    """No WebView2 required for fallback: default browser plus explicit lifetime UI."""
    import tkinter as tk
    from tkinter import messagebox
    webbrowser.open(url)
    root = tk.Tk()
    root.title('隐映 · 本地服务')
    from .app_paths import RESOURCE_ROOT
    root.iconbitmap(str(RESOURCE_ROOT / 'assets' / 'inkshield.ico'))
    root.geometry('510x230')
    root.resizable(False, False)
    tk.Label(root, text='隐映已在浏览器打开', font=('Microsoft YaHei UI', 15)).pack(pady=(25, 12))
    tk.Label(root, text='使用期间保留此窗口。关闭后将停止分析与导出。').pack()
    tk.Button(root, text='重新打开工作台', command=lambda: webbrowser.open(url)).pack(pady=12)
    tk.Button(root, text='打开数据与日志目录', command=lambda: os.startfile(str(data_root))).pack()
    def close():
        from .server import JOBS, JOB_LOCK
        with JOB_LOCK:
            busy = any(j.get('state') in ('queued', 'loading', 'analyzing', 'processing') for j in JOBS.values())
        if not busy or messagebox.askyesno('停止当前任务？', '关闭会停止当前分析或导出，确定退出？'):
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    root.mainloop()


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
