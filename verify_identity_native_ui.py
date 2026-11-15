"""Real WebView2 identity UI smoke test; isolated server/data, no browser mocks.
Run .venv/Scripts/python.exe verify_identity_native_ui.py --source PATH.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import threading
import time
import traceback
import urllib.request

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / 'runtime' / 'native-identity-verification'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['INKSHIELD_DATA_DIR'] = str(output)
    import cv2
    import uvicorn
    import webview
    import server
    fixture = output / 'identity-30frames.mp4'
    capture = cv2.VideoCapture(str(args.source))
    assert capture.isOpened(), str(args.source)
    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    writer = None
    count = 0
    try:
        for _ in range(30):
            ok, frame = capture.read()
            if not ok:
                break
            if writer is None:
                height, width = frame.shape[:2]
                writer = cv2.VideoWriter(str(fixture), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
                assert writer.isOpened()
            writer.write(frame)
            count += 1
    finally:
        capture.release()
        if writer:
            writer.release()
    assert count >= 4
    # Edge does not support OpenCV's mp4v codec. Encode the same cv2 fixture
    # with the already-installed PyAV H.264 encoder for actual playback checks.
    import av
    from fractions import Fraction
    browser_fixture = output / 'identity-30frames-h264.mp4'
    with av.open(str(fixture)) as original, av.open(str(browser_fixture), 'w') as encoded:
        target = encoded.add_stream('libx264', rate=Fraction(str(fps)).limit_denominator(100000))
        target.width, target.height = width, height
        target.pix_fmt = 'yuv420p'
        target.options = {'preset': 'ultrafast', 'crf': '18'}
        for i, frame in enumerate(original.decode(video=0)):
            frame.pts = i
            frame.time_base = Fraction(1, 1) / Fraction(str(fps)).limit_denominator(100000)
            for packet in target.encode(frame):
                encoded.mux(packet)
        for packet in target.encode(None):
            encoded.mux(packet)
    fixture = browser_fixture
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(server.app, host='127.0.0.1', port=port, log_level='warning')
    service = uvicorn.Server(config)
    worker = threading.Thread(target=service.run, kwargs={'sockets': [sock]}, daemon=True)
    worker.start()
    deadline = time.monotonic() + 30
    while not service.started:
        assert worker.is_alive(), 'Server failed to start'
        assert time.monotonic() < deadline, 'Server startup timed out'
        time.sleep(.1)
    window = webview.create_window('Inkshield native identity verification', f'http://127.0.0.1:{port}', width=1420, height=1000)
    result = {'fixture_frames': count, 'port': port, 'checks': []}
    def run():
        def js(code):
            return window.evaluate_js(code)
        def wait(expression, timeout=180):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = js(expression)
                if value:
                    return value
                time.sleep(.15)
            raise AssertionError('Timed out: ' + expression + '; state=' + str(js('({status:document.querySelector("#statusText").textContent,people:document.querySelector("#peopleNote").textContent,preview:document.querySelector("#previewFeedback").textContent,export:document.querySelector("#exportNote").textContent})')))
        def check(name, expression):
            assert js(expression), name
            result['checks'].append(name)
            print('PASS ' + name, flush=True)
        try:
            wait("typeof settings !== 'undefined' && document.readyState==='complete'", 40)
            js("window.__nativeErrors=[];window.addEventListener('error',e=>__nativeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>__nativeErrors.push(String(e.reason)));window.__nativeRequests=[];window.__realFetch=window.fetch;window.fetch=function(url,options){__nativeRequests.push({url:String(url),fields:options?.body instanceof FormData?Object.fromEntries(options.body.entries()):null});return __realFetch.apply(this,arguments)}")
            data = base64.b64encode(fixture.read_bytes()).decode('ascii')
            js("(()=>{const bytes=Uint8Array.from(atob(" + json.dumps(data) + "),c=>c.charCodeAt(0));const dt=new DataTransfer();dt.items.add(new File([bytes],'identity-30frames.mp4',{type:'video/mp4'}));document.querySelector('#file').files=dt.files;document.querySelector('#file').dispatchEvent(new Event('change',{bubbles:true}));})()")
            wait('!!media && !importing')
            check('import does not analyze', "!analysisReady && !analyzing && !__nativeRequests.some(r=>r.url.includes('/api/analyze'))")
            js("document.querySelector('#analyzeBtn').click()")
            wait('analysisReady && !!playback')
            js("if(dialog.open)document.querySelector('#progressClose').click()")
            check('real gallery and eight-field geometry', "playback.people.length>0 && document.querySelectorAll('.person-card').length===playback.people.length && playback.shapes.every(list=>list.every(s=>s.length===8))")
            wait("Array.from(document.querySelectorAll('.person-card img')).every(i=>i.complete&&i.naturalWidth>0)")
            check('all mode defaults', "settings.faceMode==='all' && settings.maskPending && Array.from(document.querySelectorAll('.person-card')).every(b=>b.disabled)")
            check('moving averages match direct replicated-border reference', """(()=>{
              for(const [w,h] of [[1,1],[1,5],[7,1],[7,5]])for(const [kx,ky] of [[3,3],[9,9],[9,1],[1,9],[1,1]]){
                const input=new Uint8ClampedArray(w*h*4);for(let i=0;i<input.length;i++)input[i]=(i*73+19)%256;
                const actual=boxBlurPixels({width:w,height:h,data:input.slice()},kx,ky).data,expected=new Uint8ClampedArray(input.length);
                for(let y=0;y<h;y++)for(let x=0;x<w;x++)for(let c=0;c<4;c++){
                  let sum=0;for(let dy=-(ky-1)/2;dy<=(ky-1)/2;dy++)for(let dx=-(kx-1)/2;dx<=(kx-1)/2;dx++)sum+=input[(Math.max(0,Math.min(h-1,y+dy))*w+Math.max(0,Math.min(w-1,x+dx)))*4+c];
                  expected[(y*w+x)*4+c]=sum/(kx*ky);
                }if(actual.some((v,i)=>v!==expected[i]))return false;
              }return boxBlurKernel(12.5,20,20)===7 && boxBlurKernel(12.5,20,20,.5)===5 && roundEven(6.5)===6 && roundEven(7.5)===8;
            })()""")
            import numpy as np
            max_difference = 0
            for width, height in [(1, 1), (1, 7), (9, 1), (11, 9)]:
                rgba = ((np.arange(width * height * 4, dtype=np.int64) * 73 + 19) % 256).astype(np.uint8).reshape(height, width, 4)
                for rx, ry, strength in [(12.5, 20, 20), (20, 15, 68), (2, 2, 100)]:
                    kernel = max(3, round(min(2 * rx, 2 * ry) * (.16 + strength * .006)) | 1)
                    for style in ['boxblur', 'horizontal', 'vertical']:
                        kx, ky = (1 if style == 'vertical' else kernel), (1 if style == 'horizontal' else kernel)
                        expected = cv2.blur(rgba, (kx, ky), borderType=cv2.BORDER_REPLICATE)
                        actual = js('(()=>{const k=boxBlurKernel(' + f'{rx},{ry},{strength}' + ');return Array.from(boxBlurPixels({width:' + str(width) + ',height:' + str(height) + ',data:new Uint8ClampedArray(' + json.dumps(rgba.reshape(-1).tolist()) + ')},' + ('1' if style == 'vertical' else 'k') + ',' + ('1' if style == 'horizontal' else 'k') + ').data)})()')
                        difference = int(np.abs(np.array(actual).reshape(rgba.shape).astype(int) - expected.astype(int)).max())
                        max_difference = max(max_difference, difference)
                        assert difference <= 1, (width, height, style, kernel, difference)
            result['cv2_max_channel_difference'] = max_difference
            result['checks'].append('36 native canvas kernel fixtures match cv2 replicated-border blur within one channel level')
            for style in ['boxblur', 'horizontal', 'vertical', 'blur', 'mosaic', 'black']:
                js("document.querySelector('[data-group=style] [data-value=" + style + "]').click()")
                wait("!preview.hidden && preview.complete && preview.naturalWidth>0 && document.querySelector('#previewFeedback').hidden")
                check('native canvas renders ' + style, "settings.style==='" + style + "' && renderPlayback(source.currentTime) && !playbackCanvas.hidden")
            check('both ellipse geometries match native black-mask pixels without changing plates', """(()=>{
              const oldW=playbackCanvas.width,oldH=playbackCanvas.height;
              try{
                playbackCanvas.width=100;playbackCanvas.height=100;
                const raw=document.createElement('canvas');raw.width=100;raw.height=100;const rc=raw.getContext('2d');rc.drawImage(source,0,0,100,100);const original=rc.getImageData(0,0,100,100).data;
                for(const faceShape of ['inscribed','circumscribed'])for(const cls of [16,21]){
                  const shape=[cls===16?'ellipse':'rectangle',50,50,20*Math.SQRT2,15*Math.SQRT2,0,cls,null];
                  renderPlayback(0,{start:0,end:1,settings:{...settings,targets:['face','plate'],style:'black',faceMode:'all',faceShape},playback:{width:100,height:100,shapes:[[shape]]}});
                  const actual=playbackCanvas.getContext('2d').getImageData(0,0,100,100).data;
                  const factor=cls===16&&faceShape==='inscribed'?1:Math.SQRT2,rx=20*factor,ry=15*factor;
                  for(let y=0;y<100;y++)for(let x=0;x<100;x++){
                    const u=x+.5-50,v=y+.5-50,t=Math.max(0,Math.min(1,cls===16?(1-Math.hypot(u/rx,v/ry))/.2:Math.min(rx-Math.abs(u),ry-Math.abs(v))/(.2*Math.min(rx,ry)))),a=Math.round(255*t*t*(3-2*t));
                    for(let c=0;c<3;c++){const i=(y*100+x)*4+c;if(Math.abs(actual[i]-Math.round(original[i]*(1-a/255)))>1)return false;}
                  }
                }return true;
              }finally{playbackCanvas.width=oldW;playbackCanvas.height=oldH;}
            })()""")
            for face_shape in ['circumscribed', 'inscribed']:
                js("document.querySelector('[data-group=faceShape] [data-value=" + face_shape + "]').click()")
                wait("!preview.hidden && preview.complete && preview.naturalWidth>0 && document.querySelector('#previewFeedback').hidden")
                check('shape preview parameter ' + face_shape, "settings.faceShape==='" + face_shape + "' && __nativeRequests.some(r=>r.url.includes('/api/preview/')&&r.url.includes('face_shape=" + face_shape + "'))")
            js("document.querySelector('[data-group=target] [data-value=face]').click()")
            check('shape controls disabled when face is off', "Array.from(document.querySelectorAll('[data-group=faceShape] button')).every(b=>b.disabled)")
            check('last target can be disabled with visible no-mask label', "settings.targets.length===0 && !document.querySelector('#targetNote').hidden && document.querySelector('#targetNote').textContent.includes('不遮罩') && !shapeSelected(['ellipse',20,20,10,10,0,16,null],settings)")
            js("document.querySelector('#frameSlider').value='15';document.querySelector('#frameSlider').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#splitBtn').click()")
            check('split retains empty targets in both children', "segments.length===2 && segments.every(s=>s.settings.targets.length===0&&s.settings.faceShape==='inscribed') && settings.targets.length===0")
            js('selectSegment(segments[0]);selectSegment(segments[1]);undoSplit()')
            check('switch and undo restore empty target snapshot', "segments.length===1 && analysisReady && settings.faceShape==='inscribed' && settings.targets.length===0 && document.querySelector('#targetNote').textContent.includes('不遮罩')")
            js("document.querySelector('#exportBtn').click();document.querySelector('[data-group=target] [data-value=face]').click()")
            check('empty-target export snapshot survives later target edit', "settings.targets.includes('face') && __nativeRequests.some(r=>r.url.includes('/api/export/')&&r.fields.target==='')")
            wait("!exporting && !document.querySelector('#download').hidden")
            check('empty-target export completion labels no masking', "document.querySelector('#exportNote').textContent.includes('不遮罩')")
            js("document.querySelector('[data-group=style] [data-value=mosaic]').click()")
            js("document.querySelector('[data-group=faceMode] [data-value=selected]').click();document.querySelector('.person-card').click();document.querySelector('#maskPending').click()")
            check('person and pending controls', "settings.faceMode==='selected' && settings.personIds.length===1 && !settings.maskPending")
            wait("!preview.hidden && preview.complete && preview.naturalWidth>0")
            wait("__nativeRequests.some(r=>r.url.includes('/api/preview/')&&r.url.includes('face_mode=selected')&&r.url.includes('mask_pending=false'))")
            result['people'] = js('playback.people.map(p=>({id:p.id,count:p.count}))')
            result['pending_count'] = js('playback.pending_count')
            js("window.__expectedPerson=settings.personIds[0];document.querySelector('#exportBtn').click();document.querySelector('[data-group=faceShape] [data-value=circumscribed]').click();document.querySelector('.person-card').click();document.querySelector('#maskPending').click()")
            check('export captures identity settings while edits continue', "exporting && settings.personIds.length===0 && settings.maskPending && __nativeRequests.some(r=>r.url.includes('/api/export/')&&r.fields.face_shape==='inscribed'&&settings.faceShape==='circumscribed'&&r.fields.face_mode==='selected'&&r.fields.person_ids===String(__expectedPerson)&&r.fields.mask_pending==='false')")
            wait("!exporting && !document.querySelector('#download').hidden")
            download = js("document.querySelector('#download').href")
            exported = output / 'selected-person-export.mp4'
            urllib.request.urlretrieve(download, exported)
            outcap = cv2.VideoCapture(str(exported))
            try:
                result['export_frames'] = int(outcap.get(cv2.CAP_PROP_FRAME_COUNT))
                assert outcap.isOpened() and result['export_frames'] == count
            finally:
                outcap.release()
            result['checks'].append('real export downloaded and decodes with exact frame count')
            js("document.querySelector('.person-card').click();document.querySelector('#frameSlider').value='15';document.querySelector('#frameSlider').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#splitBtn').click()")
            check('split resets identity choices without analysis', "segments.length===2 && segments.every(s=>!s.analysisReady&&s.settings.faceMode==='all'&&s.settings.personIds.length===0) && !analyzing")
            js("document.querySelector('#undoSplit').click()")
            check('undo restores analysis and selected identity', "segments.length===1 && analysisReady && settings.faceMode==='selected'&&settings.personIds.length===1&&!!playback")
            js("document.querySelector('[data-group=faceMode] [data-value=all]').click();document.querySelector('#frameSlider').value='0';document.querySelector('#frameSlider').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#playPause').click()")
            wait('playing && !playbackCanvas.hidden', 15)
            check('native selected-clip cached canvas playback', "!source.error && !playbackCanvas.hidden && source.muted===previewMuted")
            js('stopPlayback();seekGlobal(0);deselectClip();startPlayback()')
            wait('continuousMode && playing && !playbackCanvas.hidden', 15)
            check('native full-material continuous playback', '!clipSelected && continuousMode && !source.error && !playbackCanvas.hidden')
            js('stopPlayback()')
            result['browser_errors'] = js('__nativeErrors')
            assert not result['browser_errors'], result['browser_errors']
            result['status'] = 'passed'
        except Exception:
            result['status'] = 'failed'
            result['error'] = traceback.format_exc()
            print(result['error'], flush=True)
        finally:
            (output / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False), flush=True)
            window.destroy()
    try:
        webview.start(run, gui='edgechromium', private_mode=True, storage_path=str(output / 'webview'))
    finally:
        service.should_exit = True
        worker.join(timeout=15)
        sock.close()
    assert result.get('status') == 'passed', result.get('error', 'Window closed before completion')

if __name__ == '__main__':
    main()
