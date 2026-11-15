"""Native WebView2 formal SAM2.1 acceptance, using real OS point clicks.

Caller owns an already running service (--state or --url). No backend/model mocks.
Requires exclusive parent-assigned --inference-slot. Creates a fresh --output.
Example: python verify_sam_native_ui.py --state STATE --source VIDEO --x 646 --y 218
  --device cpu --inference-slot --output runtime/sam-native-UNIQUE
Five original-resolution frames; actual source audio is preserved in fixture.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import time
import traceback
import urllib.request

from verify_sam_packaged import ROOT, decode, endpoint, fixture_video, output_directory, sha

TITLE = 'Inkshield DOM undo diagnostic'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--state', type=Path)
    group.add_argument('--url')
    p.add_argument('--source', '--input', dest='source', required=True, type=Path)
    p.add_argument('--x', required=True, type=float)
    p.add_argument('--y', required=True, type=float)
    p.add_argument('--negative-x', type=float, default=20)
    p.add_argument('--negative-y', type=float, default=20)
    p.add_argument('--start-frame', type=int, default=0)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--output', type=Path)
    p.add_argument('--require-frozen', action='store_true')
    p.add_argument('--resume-evidence', type=Path, help='Reuse a real completed analysis for timeline/pause-only follow-up')
    p.add_argument('--inference-slot', action='store_true')
    args = p.parse_args()
    assert args.inference_slot, 'Wait for parent CPU/GPU slot before enabling --inference-slot'
    out = output_directory(args.output, 'sam-native')
    result = {'diagnostic_scope':'DOM points and direct moveCut; NOT OS acceptance','status': 'starting', 'checks': [], 'output': str(out), 'device': args.device, 'cleanup': {}}
    window = None
    try:
        import webview
        state, url = endpoint(args)
        result['service'] = state
        result['source_hashes'] = {name: sha(ROOT / name) for name in ('server.py', 'sam_service.py', 'sam_engine.py', 'index.html')}
        with urllib.request.urlopen(url, timeout=30) as response:
            result['served_index_sha256'] = hashlib.sha256(response.read()).hexdigest()
        fixture = out / 'native-five-frames.mp4'
        result['fixture'] = meta = fixture_video(args.source, fixture, 5, args.start_frame)
        for x, y in ((args.x, args.y), (args.negative_x, args.negative_y)):
            assert 0 <= x < meta['width'] and 0 <= y < meta['height'], 'Point outside original video'
        resume = json.loads(args.resume_evidence.read_text(encoding='utf-8')) if args.resume_evidence else None
        if resume:
            assert resume['served_index_sha256'] == result['served_index_sha256'], 'Resume requires identical frontend'
            assert resume['source_hashes'] == result['source_hashes'], 'Resume requires identical backend'
            completed = next(r for r in resume['requests'] if '/api/playback/' in r['url'] and r.get('http') == 200)
            resume_analysis = completed['url'].split('/api/playback/')[1].split('?')[0]
            result['resumed_real_analysis'] = {'evidence': str(args.resume_evidence), 'analysis_id': resume_analysis}
        window = webview.create_window(TITLE, url, width=1420, height=780)

        def run():
            window.move(0, 0)
            time.sleep(.3)
            def js(code):
                return window.evaluate_js(code)

            def wait(expression, timeout=180):
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    value = js(expression)
                    if value:
                        return value
                    time.sleep(.08)
                raise AssertionError('Timeout: ' + expression + '; UI=' + str(js("({status:$('#statusText').textContent,sam:$('#samStatus').textContent,frame:$('#frameSlider').value,selected:clipSelected,ready:analysisReady,analyzing})")))

            def check(name, expression):
                assert js(expression), name
                result['checks'].append(name)
                (out / 'progress.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                print('PASS ' + name, flush=True)

            def click(selector):
                js('document.querySelector(' + json.dumps(selector) + ').scrollIntoView({block:"nearest"})')
                js('document.querySelector(' + json.dumps(selector) + ').click()')
                time.sleep(.1)

            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.FindWindowW.restype = wintypes.HWND
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
            user32.SetForegroundWindow.argtypes = [wintypes.HWND]
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

            def screen_point(box):
                hwnd = user32.FindWindowW(None, TITLE)
                assert hwnd, 'Native window missing'
                user32.ShowWindow(hwnd, 9)
                foreground_result = user32.SetForegroundWindow(hwnd)
                if not foreground_result:
                    # Attach this input thread to the current foreground queue only
                    # while requesting focus, then detach before sending real input.
                    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
                    foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
                    attached = user32.AttachThreadInput(current_thread, foreground_thread, True) if foreground_thread != current_thread else False
                    try:
                        foreground_result = user32.SetForegroundWindow(hwnd)
                    finally:
                        if attached: user32.AttachThreadInput(current_thread, foreground_thread, False)
                    result.setdefault('focus_attach_events', []).append({'current_thread': current_thread, 'foreground_thread': foreground_thread, 'attached': bool(attached)})
                if user32.GetForegroundWindow() != hwnd:
                    try:
                        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)
                        foreground_result = user32.SetForegroundWindow(hwnd)
                        time.sleep(.3)
                    finally:
                        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0013)
                time.sleep(.3)
                foreground_hwnd = user32.GetForegroundWindow()
                result.setdefault('focus_events', []).append({'target_hwnd': hwnd, 'set_foreground_result': foreground_result, 'foreground_hwnd': foreground_hwnd})
                if foreground_hwnd != hwnd:
                    waiting = {'title': TITLE, 'hwnd': hwnd, 'deadline_seconds': 600, 'action': 'Activate this verification window via its title bar or taskbar; keep it foreground during the test.'}
                    (out / 'awaiting-focus.json').write_text(json.dumps(waiting, ensure_ascii=False, indent=2), encoding='utf-8')
                    print('WAITING FOR USER FOCUS: '+TITLE, flush=True)
                    deadline = time.monotonic() + 600
                    while user32.GetForegroundWindow() != hwnd and time.monotonic() < deadline:
                        time.sleep(.2)
                    foreground_hwnd = user32.GetForegroundWindow()
                    result.setdefault('user_focus_waits', []).append({**waiting, 'activated': foreground_hwnd == hwnd})
                assert foreground_hwnd == hwnd, 'Native test window did not receive foreground focus within 600 seconds'
                rect = wintypes.RECT()
                assert user32.GetClientRect(hwnd, ctypes.byref(rect))
                point = wintypes.POINT(round(box['x'] * rect.right / box['vw']), round(box['y'] * rect.bottom / box['vh']))
                assert user32.ClientToScreen(hwnd, ctypes.byref(point))
                return point.x, point.y

            def native_point(x, y):
                js('playbackCanvas.scrollIntoView({block:"nearest"})')
                box = js("(()=>{const e=playbackCanvas.hidden?preview:playbackCanvas,r=e.getBoundingClientRect(),iw=e===preview?e.naturalWidth:e.width,ih=e===preview?e.naturalHeight:e.height,s=Math.min(r.width/iw,r.height/ih),w=iw*s,h=ih*s;return {x:r.left+(r.width-w)/2+(" + str(x) + "+.5)/media.width*w,y:r.top+(r.height-h)/2+(" + str(y) + "+.5)/media.height*h,vw:innerWidth,vh:innerHeight}})()")
                box['hit'] = js('(()=>{const e=document.elementFromPoint(' + str(box['x']) + ',' + str(box['y']) + ');return e?{id:e.id,tag:e.tagName}:null})()')
                result.setdefault('point_events', []).append({'requested': [x, y], 'geometry': box})
                js("document.querySelector('#viewer').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:"+str(box['x'])+",clientY:"+str(box['y'])+"}))")
                time.sleep(.1)

            def drag_cut(frame):
                js('moveCut(segments[0].id,'+str(frame)+')')
                time.sleep(.2)

            try:
                wait("typeof samCapabilities!=='undefined' && !!samCapabilities && document.readyState==='complete'", 60)
                # Only observe genuine fetches. A single response-delivery gate below tests
                # late responses; it never changes response bytes or replaces inference.
                js("""window.__errors=[];addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));
window.__requests=[];window.__samResponses=[];window.__held=null;window.__holdNext=false;window.__realFetch=fetch;
window.fetch=async function(url,options){const record={url:String(url),method:options?.method||'GET',body:typeof options?.body==='string'?options.body:null,start:performance.now()};__requests.push(record);const response=await __realFetch.apply(this,arguments);record.http=response.status;if(String(url).includes('/api/sam/preview')){const data=await response.clone().json();record.end=performance.now();__samResponses.push({request:record,data});if(__holdNext){__holdNext=false;await new Promise(resolve=>{__held={data,release:resolve}})}}return response};
window.__draws=[];window.__originalDraw=CanvasRenderingContext2D.prototype.drawImage;CanvasRenderingContext2D.prototype.drawImage=function(image,...args){if(this.canvas===playbackCanvas)__draws.push({src:image?.src||'',at:performance.now()});return __originalDraw.call(this,image,...args)};
""")
                check('formal UI names SAM2.1 without SAM3', "$('#samControls').textContent.includes('SAM2.1') && !document.body.textContent.includes('SAM3')")
                result['capabilities'] = js('samCapabilities')
                wait("samWarmup?.state==='ready'", 180)
                result['warmup'] = js('samWarmup')
                check('advanced option adopts successful startup warmup device', "$('#samDevice').value===samWarmup.device && settings.samDevice===samWarmup.device && !!$('#samDevice').closest('details')")
                check('GPU option follows actual capability detection', "$('#samDevice option[value=cuda]').disabled===!samCapabilities.devices.find(d=>d.id==='cuda').available")
                if not js("samCapabilities.devices.find(d=>d.id==='cuda').available"):
                    check('unavailable GPU option explains why', "$('#samDevice option[value=cuda]').textContent.includes('不可用') && $('#samDevice option[value=cuda]').textContent.length>8")
                assert js('samCapabilities.available'), result['capabilities']
                assert js("samCapabilities.devices.some(d=>d.id===" + json.dumps(args.device) + '&&d.available)'), 'Requested device unavailable'
                data = base64.b64encode(fixture.read_bytes()).decode('ascii')
                js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob(" + json.dumps(data) + "),c=>c.charCodeAt(0))],'sam-native-five.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
                wait('!!media && !importing && source.readyState>=2 && clipSelected')
                check('five-frame import starts no automatic/SAM inference', "media.frames===5 && !__requests.some(r=>r.url.includes('/api/analyze')||r.url.includes('/api/sam/preview')||r.url.includes('/api/sam/analyze'))")
                if not resume:
                    js("settings.personIds=['1'];settings.faceMode='selected';saveSegment()")
                    click('#modeToggle')
                    check('switching automatic person selection to custom clears inherited IDs', "settings.mode==='custom' && settings.personIds.length===0 && settings.faceMode==='all' && selectedSegment.settings.personIds.length===0")
                    js("$('#samDevice').value=" + json.dumps(args.device) + ";$('#samDevice').dispatchEvent(new Event('change'))")
                    wait("settings.mode==='custom' && !playbackCanvas.hidden && !source.seeking")
                    check('custom mode is available before any analysis', "!analysisReady && !$('#samControls').hidden && $('#exportBtn').disabled")
                    # Delay completion of a genuine decoded seek so an OS click lands
                    # while the old image is still visible. No video pixels are replaced.
                    js("window.__seekOriginal=seekDecodedFrame;window.__seekHeld=null;seekDecodedFrame=async function(...args){const value=await __seekOriginal(...args);await new Promise(resolve=>{__seekHeld=resolve});return value};window.__scrubPrompts=JSON.stringify(settings.samPrompts);window.__scrubRequests=__requests.length;seekGlobal(1,0)")
                    wait('!!__seekHeld', 30)
                    native_point(args.x, args.y)
                    check('click during unfinished scrub never assigns old-image point to new frame', 'JSON.stringify(settings.samPrompts)===__scrubPrompts && !__requests.slice(__scrubRequests).some(r=>r.url.includes("/api/sam/preview"))')
                    js('seekDecodedFrame=__seekOriginal;__seekHeld()')
                    wait('!source.seeking', 30)
                    js('seekGlobal(0,0)')
                    wait('globalFrame===0 && !source.seeking', 30)
                    wait("samDisplayed===JSON.stringify([selectedSegment.id,0,generation]) && !playbackCanvas.hidden", 15)
                    # Keep the real source slower so the five-frame clip can be paused
                    # by the same visible transport control before naturally ending.
                    js('window.__playOriginal=source.play.bind(source);source.play=function(){source.playbackRate=.1;return __playOriginal()}')
                    click('#playPause')
                    wait('playing', 10)
                    click('#playPause')
                    wait("!playing && !startingPlayback && samDisplayed===JSON.stringify([selectedSegment.id,Number($('#frameSlider').value),generation])", 15)
                    check('raw custom playback pause restores valid point frame', 'Object.keys(settings.samPrompts).length===0 && !analysisReady')
                    js('seekGlobal(0,0)')
                    wait("samDisplayed===JSON.stringify([selectedSegment.id,0,generation])", 15)
                    js("window.__nativeClicks=[];document.addEventListener('click',event=>__nativeClicks.push({x:event.clientX,y:event.clientY,target:event.target.id}),true)")
                    native_point(args.x, args.y)
                    result['initial_click_diagnostic'] = js("({clicks:__nativeClicks,prompts:settings.samPrompts,displayed:samDisplayed,expected:JSON.stringify([selectedSegment.id,0,generation]),rect:playbackCanvas.getBoundingClientRect().toJSON(),requests:__requests.slice(-3)})")
                    wait("__requests.some(r=>r.url.includes('/api/sam/preview'))", 10)
                    wait("__samResponses.length>=1 && !samClickRunning && $('#samStatus').textContent.includes('当前帧预览已计算')", 180)
                    check('first native point immediately computes current-frame mask without propagation click', "__samResponses[0].data.cache_hit===false && !analysisReady && !__requests.some(r=>r.url.includes('/api/sam/analyze')) && !playbackCanvas.hidden && source.hidden")
                    actual = js('settings.samPrompts[0][0]')
                    # Integer screen pixels can represent several source pixels. Bound by the
                    # measured canvas scale instead of claiming subpixel OS click precision.
                    tolerance = js('Math.ceil(media.width/playbackCanvas.getBoundingClientRect().width)+1')
                    assert abs(actual['x'] - args.x) <= tolerance and abs(actual['y'] - args.y) <= tolerance and actual['label'] == 1, (actual, tolerance)
                    request_point = json.loads(js('__samResponses[0].request.body'))['prompts'][0]
                    assert request_point == actual, 'UI/API original coordinate contract changed'
                    result['native_point'] = {'requested': [args.x, args.y], 'actual': actual, 'screen_quantization_tolerance': tolerance}
                    js('window.__positivePoints=JSON.stringify(settings.samPrompts);window.__firstCanvas=playbackCanvas.toDataURL()')
                    click('#samNegative')
                    native_point(args.negative_x, args.negative_y)
                    result['negative_click_diagnostic'] = js("({clicks:__nativeClicks.slice(-4),prompts:settings.samPrompts,displayed:samDisplayed,expected:JSON.stringify([selectedSegment.id,Number($('#frameSlider').value),generation]),status:$('#samStatus').textContent,requests:__requests.slice(-3)})")
                    (out / 'progress.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                    wait('samPoints().length===2', 10)
                    wait("__requests.filter(r=>r.url.includes('/api/sam/preview')).length>=2", 10)
                    wait("__samResponses.length>=2 && !samClickRunning && $('#samStatus').textContent.includes('当前帧预览已计算')", 180)
                    check('negative native point keeps original positive and reuses same-frame features', "settings.samPrompts[0].length===2 && settings.samPrompts[0][1].label===0 && __samResponses[1].data.cache_hit===true && JSON.parse(__samResponses[1].request.body).frame===0")
                    # Hold a genuine cached correction response, then clear prompts before
                    # releasing it. The stale PNG must never reach the visible canvas.
                    js('window.__holdNext=true')
                    click('#samUndo')
                    wait('!!__held', 180)
                    check('propagation is disabled while genuine point preview is active', "$('#analyzeBtn').disabled && samClickRunning")
                    js('window.__propagateMark=__requests.length;analyzeCustom()')
                    check('active preview cannot submit conflicting propagation', '!__requests.slice(__propagateMark).some(r=>r.url.includes("/api/sam/analyze")) && !analyzing')
                    click('#samClear')
                    wait('!source.seeking && Object.keys(settings.samPrompts).length===0')
                    js('window.__drawMark=__draws.length;window.__staleMask=__held.data.mask;__held.release()')
                    wait('!samClickRunning')
                    check('late old real response is rejected after prompt revision', "!analysisReady && $('#exportBtn').disabled && !$('#samStatus').textContent.includes('当前帧预览已计算') && !__draws.slice(__drawMark).some(d=>d.src.includes(__staleMask)) && Object.keys(settings.samPrompts).length===0")
                    click('#samPositive')
                    native_point(args.x, args.y)
                    wait("!samClickRunning && $('#samStatus').textContent.includes('当前帧预览已计算')", 180)
                    check('repeated same-frame preview uses actual cached feature path', '__samResponses.at(-1).data.cache_hit===true')
                    result['preview_timings'] = js('__samResponses.map(r=>({wall_seconds:(r.request.end-r.request.start)/1000,seconds:r.data.seconds,cache_hit:r.data.cache_hit,request:JSON.parse(r.request.body)}))')
                    for index, response in enumerate(js('__samResponses.map(r=>r.data)')):
                        raw = base64.b64decode(response['mask'], validate=True)
                        (out / f'click-{index}.png').write_bytes(raw)
                    js('window.__beforePropagation=JSON.stringify(settings.samPrompts)')
                    click('#analyzeBtn')
                    wait('analysisReady && !!analysisId && !analyzing', 180)
                    js("window.__propagationMetadata=null;fetch(API+'/api/playback/'+encodeURIComponent(analysisId)).then(r=>r.json()).then(d=>{window.__propagationMetadata=d})")
                    wait('!!window.__propagationMetadata', 30)
                    if js('dialog.open'):
                        click('#progressClose')
                    wait("!$('#previewFeedback').hidden===false && ((!preview.hidden&&preview.complete)||!playbackCanvas.hidden)", 60)
                    check('five-frame real propagation has custom metadata and zero automatic geometry', "__propagationMetadata.custom===true && __propagationMetadata.sam_device===" + json.dumps(args.device) + " && __propagationMetadata.frames===5 && __propagationMetadata.shapes.every(s=>s.length===0) && __propagationMetadata.people.length===0 && !!__propagationMetadata.custom_mask_url")
                    check('propagation freezes local prompts and explicit device', "(()=>{const r=__requests.find(r=>r.url.includes('/api/sam/analyze'));const b=JSON.parse(r.body);return JSON.stringify(b.prompts)===__beforePropagation&&b.start_frame===0&&b.end_frame===5&&b.device===" + json.dumps(args.device) + '})()')
                    for frame in (1, 4, 0):
                        js(f'seekGlobal({frame},0)')
                        wait(f"globalFrame==={frame} && !source.seeking && $('#previewFeedback').hidden", 45)
                        check(f'custom selected frame {frame} displays cached processed image', 'source.hidden && ((!preview.hidden&&preview.complete)||!playbackCanvas.hidden)')
                    js("window.__protectedFrames=[];window.__observeProtectedFrame=(_,meta)=>{__protectedFrames.push({mediaTime:meta.mediaTime,presentedFrames:meta.presentedFrames,src:protectedVideo.currentSrc});protectedVideo.requestVideoFrameCallback(__observeProtectedFrame)};protectedVideo.requestVideoFrameCallback(__observeProtectedFrame)")
                    click('#playPause')
                    wait('playing || startingPlayback', 10)
                    wait('!playing && !startingPlayback', 60)
                    check('custom playback generates and presents protected video frames', "source.hidden && __requests.some(r=>r.url.includes('/api/custom-playback/')) && __protectedFrames.some(f=>f.src.includes('/api/custom-playback-video/')&&f.presentedFrames>0)")
                    result['protected_video_frames'] = js('__protectedFrames')
                    result['exports'] = []
                    for muted in ([False, True] if meta['audio'] else [True]):
                        js('previewMuted=' + str(muted).lower() + ';source.muted=previewMuted;syncControls()')
                        click('#exportBtn')
                        wait("!exporting && !$('#download').hidden", 180)
                        destination = out / ('native-mute.mp4' if muted else 'native-audio.mp4')
                        urllib.request.urlretrieve(js("$('#download').href"), destination)
                        frames, audio = decode(destination)
                        assert len(frames) == 5 and all(f.shape[:2] == (meta['height'], meta['width']) for f in frames)
                        assert audio == (meta['audio'] and not muted), (audio, muted)
                        result['exports'].append({'path': str(destination), 'frames': len(frames), 'muted': muted, 'audio_decoded': audio})
                    result['checks'].append('native export downloaded and decoded five frames with expected audio')
                else:
                    js("settings.mode='custom';settings.samPrompts={};settings.samDevice=" + json.dumps(args.device) + ";settings.personIds=[];settings.faceMode='all';saveSegment()")
                    # Read genuine ready metadata/playback from the previous completed run.
                    # Polling a ready job restores UI state without invoking inference.
                    js("analyzing=true;analysisStarted=Date.now();pollAnalysis(" + json.dumps(resume_analysis) + ",generation)")
                    wait('analysisReady && !!playback && !analyzing', 30)
                    if js('dialog.open'):
                        click('#progressClose')
                    prior = next(json.loads(r['body']) for r in resume['requests'] if '/api/sam/analyze' in r['url'])
                    js('settings.samPrompts=' + json.dumps(prior['prompts']) + ';saveSegment();syncControls()')
                    js('window.__playOriginal=source.play.bind(source);source.play=function(){source.playbackRate=.1;return __playOriginal()}')
                    check('targeted follow-up restores genuine completed custom analysis without new propagation', "analysisReady && playback.custom && !__requests.some(r=>r.url.includes('/api/sam/analyze'))")
                # Split/change interval must clear prompts on changed children. Undo
                # restores original prompt, device, cached geometry and selection state.
                js('saveSegment();window.__originalState=JSON.stringify({settings:settings,analysisId:analysisId});window.__originalPlayback=playback;window.__originalLayers=JSON.stringify(selectedSegment.layers.map(({playback,...rest})=>rest));window.__originalActiveLayer=selectedSegment.activeLayerId;window.__originalRange=[selectedSegment.start,selectedSegment.end];seekGlobal(2,0)')
                wait('globalFrame===2 && !source.seeking')
                click('#splitBtn')
                check('split custom child states are independent and clear old interval prompts', "segments.length===2 && segments.every(s=>s.settings.mode==='custom'&&Object.keys(s.settings.samPrompts).length===0&&!s.analysisReady) && segments[0].settings.samPrompts!==segments[1].settings.samPrompts")
                # Store a distinct point state through the public edit function. No
                # extra inference: negative-only points are refused before queueing.
                js("editSamPoints([{x:0,y:0,label:0}]);saveSegment();window.__rightState=JSON.stringify(selectedSegment.settings);selectSegment(segments[0]);window.__splitSnapshot=JSON.stringify(segments.map(s=>({start:s.start,end:s.end,settings:s.settings})))")
                check('segment selection isolates custom prompt state', "Object.keys(settings.samPrompts).length===0 && segments[1].settings.samPrompts[0][0].label===0")
                drag_cut(3)
                check('native moved boundary clears custom prompts only for changed intervals', 'segments[0].end===3 && segments[1].start===3 && segments.every(s=>Object.keys(s.settings.samPrompts).length===0)')
                click('#undoSplit')
                check('undo move restores isolated prompt states', 'JSON.stringify(segments.map(s=>({start:s.start,end:s.end,settings:s.settings})))===__splitSnapshot')
                click('#undoSplit')
                result['undo_split_diagnostic'] = js("({segments:segments.length,expected:JSON.parse(__originalState),actual:{settings,analysisId},playbackSame:playback===__originalPlayback,playback,originalPlayback:__originalPlayback,analysisReady,layers:selectedSegment.layers,history:splitHistory.length})")
                # Restoring a ready segment with a lazy null cache legitimately starts loadPlayback.
                # Preserve all durable layer/settings/analysis state, and verify the fetched cache
                # against the same real analysis metadata rather than requiring null identity.
                wait('!!playback && analysisReady', 30)
                check('undo split restores full custom prompt/device/cache state', "segments.length===1 && JSON.stringify({settings:settings,analysisId:analysisId})===__originalState && analysisReady && selectedSegment.activeLayerId===__originalActiveLayer && JSON.stringify([selectedSegment.start,selectedSegment.end])===JSON.stringify(__originalRange) && JSON.stringify(selectedSegment.layers.map(({playback,status,...rest})=>rest))===JSON.stringify(JSON.parse(__originalLayers).map(({status,...rest})=>rest)) && selectedSegment.layers.find(l=>l.id===__originalActiveLayer).playback===playback && JSON.stringify(playback)===JSON.stringify(window.__propagationMetadata||__originalPlayback) && playback.custom_mask_url.includes('/'+analysisId+'/')")
                js('seekGlobal(0,0)')
                wait("!source.seeking && $('#previewFeedback').hidden", 15)
                js('window.__protectedPlayOriginal=protectedVideo.play.bind(protectedVideo);protectedVideo.play=function(){protectedVideo.playbackRate=.1;return __protectedPlayOriginal()}')
                click('#playPause')
                wait('playing', 30)
                click('#playPause')
                wait("!playing && !startingPlayback && samDisplayed===JSON.stringify([selectedSegment.id,Number($('#frameSlider').value),generation])", 15)
                js('window.__pauseFrame=Number($("#frameSlider").value);window.__pauseCount=samPoints().length;window.__pauseRequestCount=__samResponses.length')
                native_point(args.x, args.y)
                wait('!analysisReady && samPoints(__pauseFrame).length===__pauseCount+1', 10)
                wait('__samResponses.length>__pauseRequestCount && !samClickRunning', 180)
                check('propagated playback pause accepts OS point on displayed frame and invalidates analysis', '!analysisReady && settings.samPrompts[String(__pauseFrame)].length===__pauseCount+1')
                result['browser_errors'] = js('__errors')
                assert not result['browser_errors'], result['browser_errors']
                result['status'] = 'passed'
            except Exception:
                result['status'] = 'failed'
                result['error'] = traceback.format_exc()
                print(result['error'], flush=True)
            finally:
                result['requests'] = js('__requests')
                result['final_status'] = js("({status:$('#statusText').textContent,sam:$('#samStatus').textContent})")
                window.destroy()
                result['cleanup']['window_destroy_requested'] = True
                result['cleanup']['service'] = 'caller-owned; not terminated'

        webview.start(run, gui='edgechromium', private_mode=True, storage_path=str(out / 'webview'))
        assert result.get('status') == 'passed', result.get('error', 'Native window closed before completion')
    except Exception:
        result['status'] = 'failed'
        result.setdefault('error', traceback.format_exc())
        raise
    finally:
        (out / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
