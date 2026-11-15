"""Isolated real Windows WebView2 layers/workspace acceptance (freeze gated).
Controlled immutable masks are fixture input only. Editing must use DOM events.
No writes to application sources, no packaging, no calls to user port 50164.
Usage: .venv-sam-build/Scripts/python THIS --prepare
       ... THIS --execute --freeze freeze.json --suite dom_suite.js
freeze.json = {"index.html":"sha256", "server.py":"sha256", ...}
The DOM suite is intentionally supplied after UI freeze, not guessed during edits.
"""
from pathlib import Path
import argparse, base64, hashlib, importlib.util, io, json, os, subprocess, sys, time, traceback, urllib.request
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LEGACY = ROOT / 'evidence/sam-timeline-native-20261109-2353/verify_timeline_native.py'
sys.path.insert(0, str(ROOT))


def legacy_module():
    spec = importlib.util.spec_from_file_location('legacy_timeline_fixture', LEGACY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def server_mode():
    os.environ['INKSHIELD_DATA_DIR'] = str(OUT / 'isolated-data')
    import server, sam_service, numpy as np, uvicorn, socket
    sam_service.WARMUP_STATE.update(state='ready', device='cpu', error=None)
    source = OUT / 'source-audio.mp4'
    from controlled_fixtures import install
    install(server, source)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    assert port != 50164
    (OUT / 'service.json').write_text(json.dumps({'pid':os.getpid(), 'url':f'http://127.0.0.1:{port}/'}), encoding='utf-8')
    uvicorn.Server(uvicorn.Config(server.app, log_level='warning')).run(sockets=[sock])


DOM_HELPERS = r"""(()=>{
window.__nativeSuite={state:'idle',checks:[],observations:[],error:null};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
window.__dom={
 async wait(test,timeout=30000){const until=performance.now()+timeout;while(performance.now()<until){const result=test();if(result)return result;await pause(40)}throw Error('DOM wait timed out: '+String(test))},
 pause,
 check(name,value,details=null){__nativeSuite.checks.push({name,passed:!!value,details});if(!value)throw Error(name+' '+JSON.stringify(details));return value},
 click(selector){const el=document.querySelector(selector);if(!el||el.disabled||el.hidden)throw Error('Unavailable DOM control '+selector);el.click();return el},
 input(selector,value){const el=document.querySelector(selector);if(!el||el.disabled)throw Error('Unavailable DOM input '+selector);el.value=String(value);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return el},
 async frame(frame){this.input('#frameSlider',frame);await this.wait(()=>Number($('#frameSlider').value)===frame);await pause(350)},
 regions(){return JSON.parse(JSON.stringify(settings.maskRegions))},
 snapshot(label){const value={label,frame:globalFrame,segments:segments.map(s=>({id:s.id,start:s.start,end:s.end,settings:cloneSettings(s.settings)})),settings:cloneSettings(settings),sample:__sample()};__nativeSuite.observations.push(value);return value},
 image(){const el=[protectedVideo,playbackCanvas,preview,source].find(e=>!e.hidden);if(!el)throw Error('No visible media');const canvas=document.createElement('canvas');canvas.width=320;canvas.height=240;canvas.getContext('2d').drawImage(el,0,0,320,240);return {element:el.id,frame:globalFrame,png:canvas.toDataURL('image/png').split(',')[1]}},
 pointer(target,type,frame,id=942){const el=typeof target==='string'?document.querySelector(target):target;if(!el)throw Error('Missing pointer target '+target);const r=timelinePlane.getBoundingClientRect();el.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,pointerId:id,pointerType:'mouse',isPrimary:true,button:0,buttons:type==='pointerup'?0:1,clientX:r.left+(frame+.2)/media.frames*timelineWidth(),clientY:el.getBoundingClientRect().top+8}))},
 async trim(selector,from,to){const el=document.querySelector(selector);if(!el)throw Error('Missing pointer target '+selector);const before=segments.map(s=>({id:s.id,start:s.start,end:s.end,settings:cloneSettings(s.settings)}));this.pointer(el,'pointerdown',from);for(let i=1;i<=12;i++){this.pointer(timelinePlane,'pointermove',Math.round(from+(to-from)*i/12));await pause(25)}this.pointer(timelinePlane,'pointerup',to);await pause(250);__nativeSuite.observations.push({kind:'DOM PointerEvent drag',selector,from,to,events:14,before,after:segments.map(s=>({id:s.id,start:s.start,end:s.end,settings:cloneSettings(s.settings)}))})},
 async scrub(name,from,to){__dragDone=false;__drag(name,from,to,1600);await this.wait(()=>__dragDone);await pause(600);const result={...__lastDrag,settled:__sample()};__nativeSuite.observations.push(result);this.check(name+' continuous visible feedback',result.distinct_visible_during>=2,result);this.check(name+' exact final frame',result.settled.frame===to,result.settled);this.check(name+' avoids full rebuild per move',result.renderTimeline_calls<result.events/2,{calls:result.renderTimeline_calls,events:result.events});if(name.startsWith('custom')){const reqs=__fetches.filter(r=>r.url.includes('/api/preview/')&&r.at>=result.begin),points=[];for(const r of reqs){points.push([r.at,1]);points.push([Math.min(r.bodyEnd??result.settled.now,r.abortAt??result.settled.now),-1])}let active=0,peak=0;for(const [,delta]of points.sort((a,b)=>a[0]-b[0]||a[1]-b[1])){active+=delta;peak=Math.max(peak,active)}result.max_preview_inflight_body=peak;this.check(name+' single in-flight preview body',peak<=1,{peak});this.check(name+' no held-drag abort storm',result.preview_aborted_during_held===0,{aborts:result.preview_aborted_during_held});this.check(name+' no busy preview response',!reqs.some(r=>r.status===429))}return result}
};
})()"""


def decode_video(path):
    import av, numpy as np
    result = {'path':str(path), 'sha256':sha(path), 'samples':{}}
    with av.open(str(path)) as container:
        result['streams'] = [{'type':s.type, 'codec':s.codec_context.name} for s in container.streams]
        for i, frame in enumerate(container.decode(video=0)):
            array = frame.to_ndarray(format='rgb24')
            # Keep both center protection and surrounding texture per frame for interval decisions.
            result['samples'][str(i)] = {'center':array[115:125,155:165].mean(axis=(0,1)).tolist(),
                                         'center_mean':float(array[115:125,155:165].mean()),
                                         'image_mean':float(array.mean())}
        result['frames'] = len(result['samples'])
    assert next(s['codec'] for s in result['streams'] if s['type']=='video') in ('h264','mpeg4')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server',action='store_true')
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--suite',type=Path)
    args = parser.parse_args()
    if args.server:
        return server_mode()
    if args.prepare:
        import av, imageio_ffmpeg, numpy, PIL, webview
        compile(LEGACY.read_text(encoding='utf-8'),str(LEGACY),'exec')
        print(json.dumps({'state':'ready_waiting_freeze','python':sys.executable,
                          'legacy_probe':str(LEGACY),'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe(),
                          'dependencies':['av','numpy','PIL','webview'],'integration_state':json.loads((OUT/'integration.json').read_text(encoding='utf-8'))['state'],
                          'server_started':False,'port_50164_untouched':True},ensure_ascii=False))
        return
    if not args.execute or not args.freeze or not args.suite:
        parser.error('--execute requires explicit --freeze and --suite')
    frozen = json.loads(args.freeze.read_text(encoding='utf-8-sig'))
    for required in ['index.html','server.py','preview_video.py','sam_service.py','mask_timeline.py','mask_layers.py','sam_engine.py']:
        assert required in frozen, 'Freeze missing '+required
    for name, expected in frozen.items():
        assert sha(ROOT/name)==expected, 'Source differs from freeze: '+name
    contract = json.loads((OUT/'integration.json').read_text(encoding='utf-8-sig'))
    assert contract['state'] == 'frozen', 'Integration pending: owner selectors and fixture binding must be frozen'
    for name in contract['source_files']:
        assert name in frozen, 'Freeze missing UI dependency '+name
    for name, expected in contract['acceptance_hashes'].items():
        assert sha(OUT/name) == expected, 'Acceptance dependency changed '+name
    assert all(contract['selectors'].values()), 'Missing owner selector'
    assert contract['backend_sam_over_five_evidence'], 'Missing backend SAM >5 evidence reference'
    assert (OUT/'frozen_adapter.js').is_file(), 'Owner-specific DOM adapter not finalized'
    adapter = (OUT/'frozen_adapter.js').read_text(encoding='utf-8')
    suite = args.suite.read_text(encoding='utf-8')
    assert 'window.runMaskTimelineAcceptance' in suite, 'DOM suite must define runMaskTimelineAcceptance'
    import imageio_ffmpeg
    command = [imageio_ffmpeg.get_ffmpeg_exe(),'-y','-nostdin','-f','lavfi','-i','testsrc2=size=320x240:rate=25:duration=6','-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-shortest',str(OUT/'source-audio.mp4')]
    with (OUT/'fixture.log').open('w') as fixture_log:
        subprocess.run(command,stdout=fixture_log,stderr=fixture_log,check=True)
    report = {'scope':'Real Windows WebView2 DOM events; controlled mask/box cache only; real backend encoding; no GPU inference or packaging',
              'hashes':frozen,'suite_sha256':sha(args.suite),'integration':contract,'input_method':'Synthetic DOM PointerEvent/WheelEvent; not OS input','passed':False}
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(sys.path)
    server_log = (OUT/'server.log').open('w')
    proc = subprocess.Popen([getattr(sys,'_base_executable',sys.executable),str(Path(__file__)),'--server'],cwd=ROOT,env=env,stdout=server_log,stderr=server_log)
    try:
        until = time.monotonic()+35
        while True:
            assert proc.poll() is None, 'Owned isolated server exited'
            try:
                state = json.loads((OUT/'service.json').read_text(encoding='utf-8'))
                if state['pid']==proc.pid:
                    assert ':50164/' not in state['url']
                    with urllib.request.urlopen(state['url'],timeout=2) as response:
                        assert hashlib.sha256(response.read()).hexdigest()==frozen['index.html']
                    break
            except Exception:
                if time.monotonic()>=until: raise
            time.sleep(.1)
        report['service'] = state
        import webview
        window = webview.create_window('Mask timeline isolated native DOM acceptance',state['url'],width=1460,height=920)
        def run():
            def js(code): return window.evaluate_js(code)
            def wait(expr,timeout=60):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    value=js(expr)
                    if "__nativeSuite.state" in expr:
                        progress=js("({state:__nativeSuite.state,checks:__nativeSuite.checks.length,last:__nativeSuite.checks.slice(-1),error:__nativeSuite.error})")
                        (OUT/'progress.json').write_text(json.dumps(progress,ensure_ascii=False),encoding='utf-8')
                    if value:return value
                    time.sleep(.07)
                raise AssertionError('Timeout '+expr)
            try:
                wait("typeof samCapabilities!=='undefined'&&!!samCapabilities&&document.readyState==='complete'")
                js(legacy_module().INSTRUMENT)
                js(DOM_HELPERS)
                data=base64.b64encode((OUT/'source-audio.mp4').read_bytes()).decode()
                js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0))],'controlled-6s.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
                wait('!!media&&!importing&&source.readyState>=2&&clipSelected')
                # Only readiness/analysis identities may be injected by owner-reviewed adapter.
                js('window.__integration='+json.dumps(contract))
                js(adapter)
                js("window.__fixtureBoot='running';Promise.resolve(__layersAdapter.bootstrap()).then(()=>__fixtureBoot='done').catch(e=>{__fixtureBoot=String(e.stack||e)})")
                wait("__fixtureBoot==='done'",30)
                for hook in ['workspace_probe.js','sam_cases.js','workspace_cases.js','tail_cases.js','pixel_capture.js']:
                    js((OUT/hook).read_text(encoding='utf-8'))
                js(suite)
                js("window.__nativeSuite.state='running';Promise.resolve().then(()=>runMaskTimelineAcceptance(__dom)).then(()=>__nativeSuite.state='done').catch(e=>{__nativeSuite.state='failed';__nativeSuite.error=String(e.stack||e)})")
                wait("['done','failed'].includes(__nativeSuite.state)",420)
                report['dom']=js('__nativeSuite')
                assert report['dom']['state']=='done',report['dom']['error']
                assert report['dom']['checks'] and all(c['passed'] for c in report['dom']['checks'])
                report['browser_errors']=js('__errors')
                assert not report['browser_errors'],report['browser_errors']
                # Suite publishes real URLs after DOM export/playback. Download and inspect codecs/frames.
                from reference_builder import build
                rules=build(OUT,js('__pixelPayload'),[0,19,20,39,40,59,60,80,99,100,119,120,139,140,149])
                screenshots=js('window.__nativeImages||[]')
                for image in screenshots:
                    (OUT/(image['name']+'.png')).write_bytes(base64.b64decode(image['png']))
                from PIL import Image
                import numpy as np
                from controlled_fixtures import ROIS
                report['jpeg_checks']=[]
                for rule in rules:
                    actual=np.asarray(Image.open(OUT/('jpeg-'+str(rule['frame'])+'.png')).convert('RGB'),dtype=float)
                    expected=np.asarray(Image.open(OUT/('reference-jpeg-'+str(rule['frame'])+'.png')).convert('RGB'),dtype=float)
                    for roi,(x0,y0,x1,y1) in ROIS.items():
                        mae=float(np.abs(actual[y0:y1,x0:x1]-expected[y0:y1,x0:x1]).mean())
                        report['jpeg_checks'].append({'frame':rule['frame'],'roi':roi,'mae':mae,'limit':12,'passed':mae<=12})
                assert all(c['passed'] for c in report['jpeg_checks']), report['jpeg_checks']
                assets=js('window.__nativeAssets||[]')
                for asset in assets: asset['pixel_expectations']=rules
                for asset in assets:
                    url=asset['url']
                    assert url.startswith(state['url']),url
                    destination=OUT/(asset['name']+'.mp4')
                    with urllib.request.urlopen(url,timeout=45) as response:
                        destination.write_bytes(response.read())
                    decoded = {'name':asset['name'],**decode_video(destination)}
                    report.setdefault('assets',[]).append(decoded)
                    expected_codec = asset.get('codec','h264' if asset['name'].endswith('protected') else 'mpeg4')
                    assert next(s['codec'] for s in decoded['streams'] if s['type']=='video') == expected_codec, decoded['streams']
                    assert decoded['frames']==asset['frames'], decoded
                    from pixel_oracle import validate_asset
                    report.setdefault('pixel_checks',[]).append(validate_asset(destination, asset, OUT))
                assert len(assets)>=2, 'DOM suite must publish protected H264 and export'
                screenshots=js('window.__nativeImages||[]')
                for image in screenshots:
                    (OUT/(image['name']+'.png')).write_bytes(base64.b64decode(image['png']))
                report['passed']=True
            except BaseException:
                report['error']=traceback.format_exc()
                try:report['dom']=js('__nativeSuite');report['failure_sample']=js('__sample()');report['browser_errors']=js('__errors')
                except Exception:pass
                print(report['error'],flush=True)
            finally:
                try:
                    report['requests']=js('__fetches')
                    for image in js('window.__nativeImages||[]'):
                        (OUT/(image['name']+'.png')).write_bytes(base64.b64decode(image['png']))
                except Exception:pass
                (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                window.destroy()
        webview.start(run,gui='edgechromium',debug=False)
    finally:
        proc.terminate()
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        server_log.close()
        report['cleanup']={'owned_server_pid':proc.pid,'exit':proc.returncode,'webview_destroyed':True}
        report['sources_unchanged']={name:sha(ROOT/name)==expected for name,expected in frozen.items()}
        report['passed']=report['passed'] and all(report['sources_unchanged'].values())
        (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report['passed'],report.get('error','Sources changed during acceptance')

if __name__=='__main__':
    main()
