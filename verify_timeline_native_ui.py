"""Native WebView2 timeline regression harness (no browser or backend mocks).

Run with .venv/Scripts/python.exe verify_timeline_native_ui.py.
--exe PATH starts an isolated packaged --serve-only service and owns its cleanup.
--state PATH uses an already running desktop-*.json service, owned by its caller.
Evidence is saved under a fresh runtime/native-timeline-* directory.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parent
TITLE = 'Inkshield native timeline verification'


def fixture_video(source, destination, count):
    import av
    with av.open(str(source)) as original, av.open(str(destination), 'w') as encoded:
        stream = original.streams.video[0]
        rate = stream.average_rate or Fraction(25)
        target = encoded.add_stream('libx264', rate=rate)
        target.width, target.height = stream.width, stream.height
        target.pix_fmt = 'yuv420p'
        target.options = {'preset': 'ultrafast', 'crf': '18'}
        actual = 0
        for i, frame in enumerate(original.decode(video=0)):
            if i >= count:
                break
            frame.pts = i
            frame.time_base = 1 / rate
            for packet in target.encode(frame):
                encoded.mux(packet)
            actual += 1
        for packet in target.encode(None):
            encoded.mux(packet)
    assert actual >= 50, 'This regression needs >=50 frames; use Desktop/5.mp4 with --frames 60'
    return actual


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.home() / 'Desktop/5.mp4')
    parser.add_argument('--frames', type=int, default=60)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--exe', type=Path)
    group.add_argument('--state', type=Path)
    args = parser.parse_args()
    if not args.source.exists():
        args.source = ROOT / 'runtime/identity-source-verification/face-identity-short.mp4'
    output = ROOT / 'runtime' / ('native-timeline-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    output.mkdir(parents=True)
    result = {'status': 'starting', 'checks': [], 'output': str(output), 'source': str(args.source), 'cleanup': {}}
    service = worker = sock = process = window = None
    try:
        fixture = output / 'timeline-h264.mp4'
        result['fixture_frames'] = fixture_video(args.source, fixture, args.frames)
        os.environ['INKSHIELD_DATA_DIR'] = str(output / 'data')
        if args.exe:
            process = subprocess.Popen([str(args.exe.resolve()), '--serve-only', '--data-dir', str(output / 'data')])
            deadline = time.monotonic() + 90
            state_path = None
            while state_path is None:
                assert process.poll() is None, 'Packaged service exited before ready'
                assert time.monotonic() < deadline, 'Packaged service startup timeout'
                candidates = list((output / 'data').glob('desktop-*.json'))
                if candidates:
                    assert len(candidates) == 1, 'Isolated service produced ambiguous state files'
                    state_path = candidates[0]
                else:
                    time.sleep(.1)
            state = json.loads(state_path.read_text(encoding='utf-8'))
            result['service'] = state
            assert state['frozen'], 'Expected frozen packaged service'
            url = state['url']
        elif args.state:
            state = json.loads(args.state.read_text(encoding='utf-8'))
            result['service'] = state
            url = state['url']
            result['cleanup']['external_service'] = 'caller-owned; not terminated'
        else:
            import uvicorn
            import server
            sock = socket.socket()
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
            service = uvicorn.Server(uvicorn.Config(server.app, host='127.0.0.1', port=port, log_level='warning'))
            worker = threading.Thread(target=service.run, kwargs={'sockets': [sock]}, daemon=True)
            worker.start()
            deadline = time.monotonic() + 40
            while not service.started:
                assert worker.is_alive() and time.monotonic() < deadline, 'Source service startup failed'
                time.sleep(.1)
            url = f'http://127.0.0.1:{port}/'
            result['service'] = {'url': url, 'frozen': False}
        import urllib.request
        with urllib.request.urlopen(url, timeout=10) as response:
            result['served_index_sha256'] = hashlib.sha256(response.read()).hexdigest()
        result['index_sha256'] = hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest()
        if args.exe:
            result['exe_sha256'] = hashlib.sha256(args.exe.read_bytes()).hexdigest()
        import webview
        window = webview.create_window(TITLE, url, width=1420, height=780)

        def run():
            def js(code):
                return window.evaluate_js(code)

            def wait(expression, timeout=180):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    value = js(expression)
                    if value:
                        return value
                    time.sleep(.06)
                raise AssertionError('Timeout: ' + expression + '; ' + str(js("({status:$('#statusText').textContent,feedback:$('#previewFeedback').textContent,time:source.currentTime,seeking:source.seeking})")))

            def check(name, expression):
                value = js(expression)
                assert value, name
                result['checks'].append(name)
                print('PASS ' + name, flush=True)

            user32 = ctypes.windll.user32
            user32.FindWindowW.restype = wintypes.HWND
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

            def point(selector, fraction=.5):
                box = js("(()=>{const r=document.querySelector(" + json.dumps(selector) + ").getBoundingClientRect();return {x:r.left+r.width*" + str(fraction) + ",y:r.top+r.height/2,w:innerWidth,h:innerHeight}})()")
                hwnd = user32.FindWindowW(None, TITLE)
                assert hwnd, 'Native window missing'
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                p = wintypes.POINT(round(box['x'] * rect.right / box['w']), round(box['y'] * rect.bottom / box['h']))
                user32.ClientToScreen(hwnd, ctypes.byref(p))
                return p.x, p.y

            def mouse(x, y):
                user32.SetCursorPos(int(x), int(y))

            def click(selector):
                js('document.querySelector(' + json.dumps(selector) + ').scrollIntoView({block:"nearest"})')
                js('document.querySelector(' + json.dumps(selector) + ').click()')
                time.sleep(.12)

            def key(code):
                user32.keybd_event(code, 0, 0, 0)
                user32.keybd_event(code, 0, 2, 0)
                time.sleep(.12)

            def drag(selector, frame, cancel=False):
                js('document.querySelector(' + json.dumps(selector) + ').scrollIntoView({block:"center"})')
                time.sleep(.1)
                start = point(selector)
                destination = point('#timelinePlane', frame / js('media.frames'))
                mouse(*start)
                user32.mouse_event(2, 0, 0, 0, 0)
                time.sleep(.15)
                try:
                    assert js('!!cutDrag'), 'OS pointerdown missed cut marker: ' + str(js("({active:document.activeElement?.tagName,rect:document.querySelector('.cut-marker').getBoundingClientRect().toJSON(),vw:innerWidth,vh:innerHeight})"))
                    for step in range(1, 9):
                        mouse(start[0] + (destination[0] - start[0]) * step / 8, start[1])
                        time.sleep(.025)
                    if cancel:
                        key(0x1B)
                finally:
                    user32.mouse_event(4, 0, 0, 0, 0)
                time.sleep(.15)

            try:
                wait("typeof settings!=='undefined' && document.readyState==='complete'", 40)
                js("window.__errors=[];addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));window.__requests=[];const originalFetch=window.fetch;window.fetch=function(url,options){__requests.push(String(url));return originalFetch.apply(this,arguments)}")
                data = base64.b64encode(fixture.read_bytes()).decode('ascii')
                js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(" + json.dumps(data) + "),c=>c.charCodeAt(0))],'timeline.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
                wait('!!media && !importing && source.readyState>=2')
                check('import does not infer', "!analysisReady && !__requests.some(u=>u.includes('/api/analyze'))")
                click('#analyzeBtn')
                print('ANALYZE ' + str(js("({analyzing,status:$('#statusText').textContent,requests:__requests})")), flush=True)
                wait('analysisReady && !!playback', 90)
                if js('dialog.open'):
                    click('#progressClose')
                wait("!playbackCanvas.hidden && $('#previewFeedback').hidden", 30)
                js("window.__originalCache=playback;window.__analysisRequests=__requests.filter(u=>u.includes('/api/analyze')).length;window.__previewRequests=__requests.filter(u=>u.includes('/api/preview/')).length;window.__visibleSamples=[];window.__monitor=true;window.__sample=()=>{if(!__monitor)return;__visibleSamples.push({canvas:!playbackCanvas.hidden,image:!preview.hidden&&preview.complete,raw:!source.hidden,seeking:source.seeking});requestAnimationFrame(__sample)};__sample();window.__beforePixels=playbackCanvas.toDataURL();seekGlobal(37,180);window.__heldPixels=playbackCanvas.toDataURL()")
                check('pending seek retains visible old masked pixels', '!playbackCanvas.hidden && source.hidden && __beforePixels===__heldPixels')
                # Real native slider interaction, then overlapping programmatic seeks to stress latest-wins.
                click('#frameSlider')
                js('seekGlobal(4,0);setTimeout(()=>seekGlobal(48,0),8);setTimeout(()=>seekGlobal(12,0),16);setTimeout(()=>seekGlobal(43,0),24)')
                wait("!source.seeking && Math.abs(source.currentTime-43/media.fps)<.51/media.fps && globalFrame===43 && !playbackCanvas.hidden && $('#previewFeedback').hidden", 30)
                js('window.__monitor=false')
                check('rapid seek latest frame wins', 'globalFrame===43 && Number($("#frameSlider").value)===43')
                check('no hidden-all or unmasked raw flash during cached scrubbing', '__visibleSamples.length>0 && __visibleSamples.every(s=>(s.canvas||s.image)&&!s.raw)')
                check('cached scrubbing sends zero JPEG preview requests', "__requests.filter(u=>u.includes('/api/preview/')).length===__previewRequests")
                check('cached scrubbing reuses inference cache', "playback===__originalCache && __requests.filter(u=>u.includes('/api/analyze')).length===__analysisRequests")
                js("window.__movingTimes=[];window.__renderedTimes=[];window.__renderBefore=renderPlayback;renderPlayback=function(t,...rest){const ok=__renderBefore(t,...rest);if(ok)__renderedTimes.push({frame:Math.round(t*media.fps),at:performance.now(),tick:__movingTicks});return ok};window.__movingTicks=0;window.__movingTimer=setInterval(()=>{__movingTimes.push(source.currentTime);seekGlobal((__movingTicks*3)%media.frames,80);if(++__movingTicks>=40){clearInterval(__movingTimer);seekGlobal(43,0)}},25)")
                wait('__movingTicks>=40', 10)
                wait("!source.seeking && globalFrame===43 && $('#previewFeedback').hidden", 30)
                check('sustained 25ms scrubbing renders intermediate decoded frames', 'new Set(__renderedTimes.filter(t=>t.tick<40).map(t=>t.frame)).size>=4')
                js("window.__sameFrame=globalFrame;settings.style='black';schedulePreview(0)")
                wait("!source.seeking && $('#previewFeedback').hidden", 15)
                check('same-frame settings redraw completes', 'globalFrame===__sameFrame && !playbackCanvas.hidden && source.hidden')
                result['sustained_scrub_decoded_frames'] = js('Array.from(new Set(__movingTimes.map(t=>Math.round(t*media.fps))))')
                result['scrub_samples'] = js('__visibleSamples')
                result['seek_time'] = js('source.currentTime')
                check('visible canvas matches deterministic current-frame cached render', "(()=>{const before=playbackCanvas.toDataURL();renderPlayback(43/media.fps);return before===playbackCanvas.toDataURL()})()")
                result['rendered_intermediate_frames'] = js('__renderedTimes')
                for style in ['boxblur', 'horizontal', 'vertical', 'blur', 'mosaic', 'black']:
                    click('[data-group=style] [data-value=' + style + ']')
                    wait("!playbackCanvas.hidden && $('#previewFeedback').hidden", 15)
                    check('cached settings redraw ' + style, "settings.style===" + json.dumps(style) + ' && playback===__originalCache && source.hidden')
                for shape in ['inscribed', 'circumscribed']:
                    click('[data-group=faceShape] [data-value=' + shape + ']')
                    wait("!playbackCanvas.hidden && $('#previewFeedback').hidden", 15)
                    check('cached ellipse setting ' + shape, 'settings.faceShape===' + json.dumps(shape) + ' && playback===__originalCache')
                js("settings.targets=[];settings.faceMode='selected';settings.personIds=[];settings.maskPending=false;saveSegment();syncControls();schedulePreview(0)")
                wait("!playbackCanvas.hidden && $('#previewFeedback').hidden", 15)
                check('explicit empty targets and identity choices survive cached redraw', "settings.targets.length===0 && settings.personIds.length===0 && !settings.maskPending && !shapeSelected(['ellipse',20,20,10,10,0,16,null],settings)")
                click('#exportBtn')
                wait("!exporting && !$('#download').hidden", 180)
                import urllib.request
                import av
                exported = output / 'empty-target-export.mp4'
                urllib.request.urlretrieve(js("$('#download').href"), exported)
                with av.open(str(exported)) as decoded:
                    result['export_frames'] = sum(1 for _ in decoded.decode(video=0))
                assert result['export_frames'] == result['fixture_frames'], 'Export exact frame count'
                result['checks'].append('empty-target export decodes with exact frame count')
                # Boundary tests use public DOM controls and real pointer capture.
                run_boundary_tests(js, wait, check, click, key, drag, result)
                result['browser_errors'] = js('__errors')
                assert not result['browser_errors'], result['browser_errors']
                result['status'] = 'passed'
            except Exception:
                result['status'] = 'failed'
                result['error'] = traceback.format_exc()
                print(result['error'], flush=True)
            finally:
                result['requests'] = js('__requests')
                window.destroy()
                result['cleanup']['window_destroy_requested'] = True

        webview.start(run, gui='edgechromium', private_mode=True, storage_path=str(output / 'webview'))
    except Exception:
        result['status'] = 'failed'
        result['error'] = traceback.format_exc()
    finally:
        if service:
            service.should_exit = True
        if worker:
            worker.join(timeout=20)
            result['cleanup']['service_thread_stopped'] = not worker.is_alive()
        if sock:
            sock.close()
        if process:
            # PyInstaller one-file launcher owns a child service process.
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=20)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            result['cleanup']['packaged_process_stopped'] = process.poll() is not None
            from urllib.parse import urlparse
            if result.get('service', {}).get('url'):
                endpoint = urlparse(result['service']['url'])
                with socket.socket() as probe:
                    probe.settimeout(1)
                    result['cleanup']['service_listener_closed'] = probe.connect_ex((endpoint.hostname, endpoint.port)) != 0
        (output / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
    assert result.get('status') == 'passed', result.get('error', 'Window closed before completion')
    assert all(value is not False for value in result['cleanup'].values()), result['cleanup']


def run_boundary_tests(js, wait, check, click, key, drag, result):
    check('editable boundary contract exists', "typeof moveCut==='function' && typeof timelineSnapshot==='function' && !!$('#cutLane') && !!$('#deleteCut')")
    js('seekGlobal(20,0)')
    click('#splitBtn')
    js('seekGlobal(40,0)')
    click('#splitBtn')
    check('split creates continuous nonempty intervals', 'segments.length===3 && segments[0].start===0 && segments[2].end===media.frames && segments.every((s,i)=>s.end-s.start>=1&&(!i||segments[i-1].end===s.start))')
    # Analyze real disjoint segments so invalidation is checked against real cache objects.
    for index in range(3):
        js(f'selectSegment(segments[{index}])')
        click('#analyzeBtn')
        wait('analysisReady && !!playback', 300)
        if js('dialog.open'):
            click('#progressClose')
        wait("!playbackCanvas.hidden && $('#previewFeedback').hidden", 30)
    js("selectSegment(segments[0]);seekGlobal(5,0)")
    wait("!source.seeking && !playbackCanvas.hidden && $('#previewFeedback').hidden", 20)
    js('window.__crossStart=performance.now();seekGlobal(45,0)')
    check('cross-segment analyzed seek keeps raw source hidden', 'source.hidden')
    wait("!source.seeking && globalFrame===45 && !playbackCanvas.hidden && $('#previewFeedback').hidden", 8)
    result['cross_segment_ms'] = js('performance.now()-__crossStart')
    js("selectSegment(segments[0]);settings.style='black';settings.targets=[];settings.faceMode='selected';settings.personIds=[];settings.maskPending=false;settings.faceShape='inscribed';saveSegment();selectSegment(segments[1]);settings.style='horizontal';saveSegment();selectSegment(segments[2]);settings.style='vertical';saveSegment();window.__segState=()=>JSON.stringify(segments.map(s=>({...s,playback:s.playback?{frames:s.playback.frames,start_frame:s.playback.start_frame}:null})));window.__beforeEdit=__segState();window.__refs=segments.map(s=>s.playback);window.__historyCount=splitHistory.length;window.__leftId=segments[0].id;window.__middleId=segments[1].id")
    first = '.cut-marker:first-child'
    click(first)
    check('boundary selection is a cache-preserving no-op', '__segState()===__beforeEdit && segments.every((s,i)=>s.playback===__refs[i]) && splitHistory.length===__historyCount && selectedCutId===__leftId')
    drag(first, 27, cancel=True)
    check('Escape cancels drag without mutating intervals or cache', '__segState()===__beforeEdit && segments.every((s,i)=>s.playback===__refs[i]) && splitHistory.length===__historyCount')
    drag(first, 26)
    check('native boundary drag resizes adjacent intervals continuously', 'segments[0].end===segments[1].start && Math.abs(segments[0].end-26)<=1 && segments.every(s=>s.end>s.start)')
    check('drag invalidates affected two caches only', '!segments[0].analysisReady && !segments[1].analysisReady && !segments[0].playback && !segments[1].playback && segments[2].playback===__refs[2] && segments[2].analysisReady')
    check('drag preserves unaffected complete segment state and affected nonidentity settings', "JSON.stringify({...segments[2],playback:{frames:segments[2].playback.frames,start_frame:segments[2].playback.start_frame}})===JSON.stringify(JSON.parse(__beforeEdit)[2]) && segments[0].settings.targets.length===0 && segments[0].settings.style==='black' && segments[0].settings.faceShape==='inscribed' && segments[1].settings.style==='horizontal'")
    click('#undoSplit')
    check('undo drag restores all segment state and cache objects', '__segState()===__beforeEdit && segments.every((s,i)=>s.playback===__refs[i])')
    # Clamp both extremes via real captured mouse drags.
    drag(first, 0)
    check('left drag clamp leaves minimum one frame', 'segments[0].end===1 && segments[1].start===1 && segments[0].end-segments[0].start===1')
    click('#undoSplit')
    drag(first, 48)
    check('right drag clamp leaves minimum one frame', 'segments[0].end===39 && segments[1].start===39 && segments[1].end-segments[1].start===1')
    click('#undoSplit')
    click('.cut-marker:last-child')
    check('only explicitly selected boundary is targeted', 'selectedCutId===__middleId')
    js('window.__beforeMerge=timelineSnapshot();window.__middleConfig=JSON.stringify(segments[1].settings);window.__leftCache=segments[0].playback')
    click('#deleteCut')
    check('delete selected second boundary merges only middle and right', 'segments.length===2 && segments[0].end===20 && segments[1].start===20 && segments[1].end===media.frames && segments[0].playback===__leftCache')
    check('merge explicitly inherits left-side configuration', 'JSON.stringify(segments[1].settings)===__middleConfig && !segments[1].analysisReady && !segments[1].playback')
    click('#undoSplit')
    check('undo merge restores full snapshot including cache and cut selection', '__segState()===__beforeEdit && segments.every((s,i)=>s.playback===__refs[i]) && selectedCutId===__middleId')
    # Native Delete with no selected cut must not silently pick a neighbor.
    js('selectedCutId=null;renderTimeline()')
    click('#timelineRuler')
    js('window.__noSelectionBefore=__segState();window.__noSelectionHistory=splitHistory.length')
    key(0x2E)
    check('Delete without selected cut is a no-op', '__segState()===__noSelectionBefore && splitHistory.length===__noSelectionHistory')
    js('selectSegment(segments[0]);deselectClip();globalFrame=45;window.__unselectedSnapshot=timelineSnapshot();moveCut(segments[0].id,25);undoSplit()')
    check('undo restores deselected global playhead beyond old selected segment', 'globalFrame===45 && !clipSelected && selectedSegment.start<=45 && selectedSegment.end>45')
    result['final_segments'] = js('segments.map(s=>({id:s.id,start:s.start,end:s.end,analysisReady:s.analysisReady,settings:s.settings}))')


if __name__ == '__main__':
    main()
