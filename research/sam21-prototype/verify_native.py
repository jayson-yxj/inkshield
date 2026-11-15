"""Verify the actual SAM2 prototype in WebView2 against an already-running service.
No inference mocks. Run with the dedicated environment:
python verify_native.py --url http://127.0.0.1:PORT --source VIDEO --x 646 --y 218
Only the first five frames are uploaded. The service must be idle before this test.
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import traceback
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--x', type=int, default=646)
    parser.add_argument('--y', type=int, default=218)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent / 'runtime' / 'native-verification')
    args = parser.parse_args()
    import cv2
    import webview

    args.output.mkdir(parents=True, exist_ok=True)
    fixture = args.output / 'native-five-frames.mp4'
    capture = cv2.VideoCapture(str(args.source))
    assert capture.isOpened(), f'Cannot open source: {args.source}'
    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    writer = None
    count = 0
    try:
        for _ in range(5):
            ok, frame = capture.read()
            if not ok:
                break
            if writer is None:
                height, width = frame.shape[:2]
                assert 0 <= args.x < width and 0 <= args.y < height, 'Target coordinate outside source'
                writer = cv2.VideoWriter(str(fixture), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
                assert writer.isOpened(), 'Fixture encoder failed'
            writer.write(frame)
            count += 1
    finally:
        capture.release()
        if writer:
            writer.release()
    assert count == 5, f'Expected five input frames, got {count}'
    window = webview.create_window('SAM 2.1 native prototype verification', args.url, width=1360, height=980)
    result = {'checks': [], 'url': args.url, 'fixture_frames': count, 'point': [args.x, args.y]}

    def run() -> None:
        def js(code):
            return window.evaluate_js(code)

        def wait(expression, timeout=180):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = js(expression)
                if value:
                    return value
                time.sleep(.15)
            raise AssertionError('Timed out: ' + expression + '; UI=' + str(js("({status:ui.statusText.textContent,busy:state.busy,ready:state.ready,frame:state.frame,loading:state.loading})")))

        def check(name, expression):
            assert js(expression), name
            result['checks'].append(name)
            print('PASS ' + name, flush=True)

        def click_point(x, y):
            js("(()=>{const r=ui.canvas.getBoundingClientRect();ui.canvas.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,clientX:r.left+" + str(x) + "/state.video.width*r.width,clientY:r.top+" + str(y) + "/state.video.height*r.height}));window.__pointSnapshot={ready:state.ready,exportDisabled:ui.export.disabled,downloadHidden:ui.download.hidden,mode:ui.viewMode.value,overlay:!!state.overlay,renderedFrame:state.renderedFrame};})()")

        try:
            wait("typeof state !== 'undefined' && document.readyState==='complete'", 40)
            js("window.__nativeErrors=[];window.addEventListener('error',e=>__nativeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>__nativeErrors.push(String(e.reason)));window.__nativeRequests=[];window.__realFetch=window.fetch;window.fetch=function(url,options){__nativeRequests.push({url:String(url),method:options?.method||'GET'});return __realFetch.apply(this,arguments)}")
            data = base64.b64encode(fixture.read_bytes()).decode('ascii')
            js("(()=>{const bytes=Uint8Array.from(atob(" + json.dumps(data) + "),c=>c.charCodeAt(0));const dt=new DataTransfer();dt.items.add(new File([bytes],'native-five-frames.mp4',{type:'video/mp4'}));ui.upload.files=dt.files;ui.upload.dispatchEvent(new Event('change',{bubbles:true}));})()")
            wait('!!state.video && !state.busy && !state.loading && state.renderedFrame===0')
            check('real five-frame import does not start inference', "state.video.frames===5 && !state.ready && !__nativeRequests.some(r=>r.url.includes('/api/segment/'))")
            check('native canvas fits without distorting letterboxed image', "(()=>{const r=ui.canvas.getBoundingClientRect(),s=ui.stage.getBoundingClientRect();return Math.abs(r.width/r.height-state.video.width/state.video.height)<0.002&&r.width<=s.width+1&&r.height<=s.height+1&&Math.abs((r.left+r.right)/2-(s.left+s.right)/2)<1&&Math.abs((r.top+r.bottom)/2-(s.top+s.bottom)/2)<1})()")
            click_point(args.x, args.y)
            check('native pointer maps exactly to original coordinate', f'state.prompts[0].length===1 && state.prompts[0][0].x==={args.x} && state.prompts[0][0].y==={args.y} && state.prompts[0][0].label===1')
            js('ui.negative.click()')
            click_point(max(0, args.x - 100), max(0, args.y - 100))
            check('negative point and point list are frame-local', "state.prompts[0].length===2 && state.prompts[0][1].label===0 && ui.pointList.children.length===2")
            js('ui.undo.click()')
            check('undo removes only last point', 'state.prompts[0].length===1 && state.prompts[0][0].label===1')
            js('selectFrame(1)')
            wait('!state.loading && state.renderedFrame===1')
            click_point(max(0, args.x - 100), max(0, args.y - 100))
            check('negative-only prompted frame blocks propagation with explanation', "ui.segment.disabled && ui.readyHint.textContent.includes('只有负点')")
            js('ui.clearFrame.click();selectFrame(0)')
            wait('!state.loading && state.renderedFrame===0')
            check('clearing negative-only frame restores propagation', '!ui.segment.disabled && state.prompts[0].length===1 && !state.prompts[1]')
            js('ui.segment.click()')
            check('propagation locks all writes', 'state.busy && ui.upload.disabled && ui.positive.disabled && ui.style.disabled && ui.export.disabled')
            wait('!state.busy', 1200)
            check('real model propagation completes', "state.ready && __nativeRequests.filter(r=>r.url.includes('/api/segment/')).length===1")
            wait('!state.loading && state.renderedFrame===state.frame')
            check('native overlay loads at original dimensions', '!!state.overlay && state.overlay.naturalWidth===state.video.width && state.overlay.naturalHeight===state.video.height')
            result['empty_frames'] = js('state.emptyFrames')
            result['video'] = js('state.video')
            for frame_number in range(5):
                js(f'selectFrame({frame_number})')
                wait(f'!state.loading && state.renderedFrame==={frame_number}')
                check(f'frame {frame_number} overlay loads', '!!state.base && !!state.overlay')
            js("ui.viewMode.value='processed';ui.viewMode.dispatchEvent(new Event('change'))")
            wait("!state.loading && state.visibleMode==='processed' && !!state.base")
            check('actual processed JPEG loads', "state.base.naturalWidth===state.video.width && __nativeRequests.some(r=>r.url.includes('/api/job/'))")
            js('ui.export.click()')
            wait('!state.busy', 180)
            check('real export provides local download', "!ui.download.hidden && ui.download.href.includes('/api/download/')")
            download = js('ui.download.href')
            exported = args.output / 'native-export.mp4'
            urllib.request.urlretrieve(download, exported)
            output_capture = cv2.VideoCapture(str(exported))
            decoded = 0
            try:
                while True:
                    ok, frame = output_capture.read()
                    if not ok:
                        break
                    assert frame.shape[:2] == (height, width), frame.shape
                    decoded += 1
            finally:
                output_capture.release()
            assert decoded == count, f'Export decoded {decoded}, expected {count}'
            result['checks'].append('downloaded export decodes five frames with original dimensions')
            result['download'] = download
            result['decoded_export_frames'] = decoded
            # Mutate while a processed preview is visible: old pixels and export must disappear immediately.
            js('ui.positive.click()')
            click_point(args.x, args.y)
            check('correction invalidates ready/export and processed preview synchronously', "!__pointSnapshot.ready && __pointSnapshot.exportDisabled && __pointSnapshot.downloadHidden && __pointSnapshot.mode==='overlay' && !__pointSnapshot.overlay && __pointSnapshot.renderedFrame===-1")
            wait('!state.loading && state.renderedFrame===state.frame')
            js('ui.clearFrame.click()')
            check('clear current frame removes only its prompts', '!state.prompts[state.frame] && !state.ready && ui.download.hidden')
            check('original positive on frame zero is retained', 'state.prompts[0].length===1')
            result['browser_errors'] = js('__nativeErrors')
            assert not result['browser_errors'], result['browser_errors']
            result['status'] = 'passed'
        except Exception:
            result['status'] = 'failed'
            result['error'] = traceback.format_exc()
            print(result['error'], flush=True)
        finally:
            (args.output / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False), flush=True)
            window.destroy()

    webview.start(run, gui='edgechromium', private_mode=True, storage_path=str(args.output / 'webview'))
    assert result.get('status') == 'passed', result.get('error', 'Window closed before verification finished')


if __name__ == '__main__':
    main()
