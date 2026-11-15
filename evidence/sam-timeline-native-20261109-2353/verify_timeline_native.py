"""Actual WebView2 DOM PointerEvent timeline acceptance. Execute only after parent HTML freeze.
Reuse controlled immutable-mask server and real encoder from smooth-native acceptance.
Synthetic pointer capture shim only; no application file changes and no GPU inference.
"""
from pathlib import Path
import argparse, base64, hashlib, importlib.util, json, os, subprocess, sys, time, traceback, urllib.request
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
BASE=ROOT/'evidence/sam-smooth-playback-20261109-2340/verify_smooth_native.py'

def server_mode():
    spec=importlib.util.spec_from_file_location('smooth_fixture',BASE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT;module.server_mode()

def main():
    p=argparse.ArgumentParser();p.add_argument('--server',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--html-sha256');a=p.parse_args()
    if a.server:return server_mode()
    if not a.execute or not a.html_sha256:p.error('Requires explicit parent freeze hash and --execute')
    actual=hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest()
    assert actual==a.html_sha256,(actual,a.html_sha256)
    import imageio_ffmpeg
    cmd=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-nostdin','-f','lavfi','-i','testsrc2=size=320x240:rate=25:duration=6','-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-shortest',str(OUT/'source-audio.mp4')]
    with (OUT/'fixture.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=log,check=True)
    report={'scope':'Actual Windows WebView2, DOM pointer events, synthetic immutable masks, real encoder. No SAM inference or model quality claim. Pointer capture API shim for synthetic pointer only.','html_sha256':actual,'cases':[],'checks':[]}
    env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join(sys.path+[str(ROOT)])
    log=(OUT/'server.log').open('w');proc=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),str(Path(__file__)),'--server'],cwd=ROOT,env=env,stdout=log,stderr=log)
    try:
        deadline=time.monotonic()+30
        while True:
            assert proc.poll() is None,'isolated server exited'
            try:
                state=json.loads((OUT/'service.json').read_text())
                if state['pid']==proc.pid:
                    with urllib.request.urlopen(state['url'],timeout=1) as r:served=hashlib.sha256(r.read()).hexdigest()
                    assert served==actual
                    break
            except Exception:pass
            assert time.monotonic()<deadline;time.sleep(.1)
        report['service']=state;report['served_html_sha256']=served
        import webview
        window=webview.create_window('Inkshield continuous timeline DOM acceptance',state['url'],width=1420,height=860)
        def run():
            def js(code):return window.evaluate_js(code)
            def wait(expr,timeout=45):
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    v=js(expr)
                    if v:return v
                    time.sleep(.05)
                raise AssertionError('Timeout '+expr+' STATE '+str(js("({globalFrame,analysisReady,mode:settings.mode,status:$('#statusText').textContent,feedback:$('#previewFeedback').textContent})")))
            def check(name,expr):
                v=js(expr);assert v,name+' '+str(v);report['checks'].append(name)
            def drag(name,start,end,duration=1500):
                js('window.__dragDone=false;window.__lastDrag=null;__drag('+json.dumps(name)+','+str(start)+','+str(end)+','+str(duration)+')')
                wait('__dragDone',15);time.sleep(.7)
                result=js('__lastDrag');result['settled']=js('__sample()')
                result['preview_requests_final']=js('__fetches.filter(r=>r.url.includes("/api/preview/")&&r.at>=__lastDrag.begin)')
                reqs=result['preview_requests_final'];points=[]
                for r in reqs:
                    points.append((r['at'],1));points.append((min(r.get('bodyEnd',result['settled']['now']),r.get('abortAt',result['settled']['now'])),-1))
                active=peak=0
                for _,delta in sorted(points):active+=delta;peak=max(peak,active)
                result['max_preview_inflight_body']=peak;result['preview_aborted_final']=sum(bool(r['aborted']) for r in reqs)
                report['cases'].append(result)
                png=js("(()=>{const el=[protectedVideo,playbackCanvas,preview,source].find(e=>!e.hidden);if(!el)return null;const c=document.createElement('canvas');c.width=320;c.height=240;c.getContext('2d').drawImage(el,0,0,320,240);return c.toDataURL('image/png').split(',')[1]})()")
                if png:(OUT/(name+'-final.png')).write_bytes(base64.b64decode(png))
                print(name,json.dumps({k:v for k,v in result.items() if k!='samples'},ensure_ascii=False),flush=True)
                assert result['elapsed_ms']>=1000,name+' duration'
                assert result['distinct_visible_during']>=2,name+' no visible updates during held drag'
                assert result['settled']['frame']==end,name+' final global frame incorrect'
                assert result['settled']['slider']==end-result['settled']['segStart'],name+' final slider incorrect'
                return result
            try:
                wait("typeof samCapabilities!=='undefined'&&!!samCapabilities&&document.readyState==='complete'",60)
                js(INSTRUMENT)
                data=base64.b64encode((OUT/'source-audio.mp4').read_bytes()).decode()
                js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0))],'controlled-6s.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
                wait('!!media&&!importing&&source.readyState>=2&&clipSelected')
                js("(()=>{const left=makeSegment(0,75),right=makeSegment(75,150);left.settings.mode='custom';left.settings.targets=['custom'];left.settings.style='black';left.analysisId='controlled-custom';left.analysisReady=true;left.status='已分析';right.analysisId='controlled-auto';right.analysisReady=true;right.status='已分析';segments=[left,right];globalFrame=80;selectSegment(right,false)})()")
                wait('!!playback&&!playbackCanvas.hidden')
                drag('automatic_cached',80,140)
                check('automatic final decoded source frame 140','decodedSourceFrame===140')
                js("segments[1].analysisReady=false;segments[1].analysisId='';segments[1].playback=null;selectSegment(segments[1],false)")
                wait('!analysisReady&&!source.hidden');drag('unanalyzed_raw',80,140)
                check('raw final decoder time matches frame 140','Math.abs(source.currentTime-140/25)<.05')
                js("globalFrame=0;selectSegment(segments[0],false);$('#playPause').click()")
                wait('playing&&!startingPlayback&&!protectedVideo.hidden',60)
                wait('protectedVideo.currentTime>.25');js("$('#playPause').click()")
                check('real encoder cached protected video','protectedSources.size>=1&&protectedVideo.videoWidth===320')
                cached=drag('custom_cached_protected_video',5,65)
                js('protectedSources.clear();protectedVideo.hidden=true')
                jpeg=drag('custom_uncached_jpeg',5,65)
                for measured in [cached,jpeg]:
                    assert measured['max_preview_inflight_body']<=1,measured['name']+' multiple in-flight JPEG bodies'
                    assert measured['preview_aborted_during_held']==0,measured['name']+' abort during held same-segment drag'
                    assert measured['preview_aborted_final']<=2,measured['name']+' abort storm (initial/final cancellation only)'
                    assert measured['renderTimeline_calls']<measured['events']/2,measured['name']+' timeline rebuild per move'
                report['checks'].append('both custom cache states single in-flight JPEG, no same-segment abort, no per-move timeline rebuild')
                check('custom final JPEG frame ownership','samDisplayed===JSON.stringify([selectedSegment.id,65,generation])')
                # Compare visible final image to a fresh real backend frame-65 JPEG, not just its stamp.
                import io, numpy as np
                from PIL import Image
                reference_url=state['url']+'api/preview/controlled-custom?frame=65&target=custom&style=black&strength='+str(js('settings.strength'))+'&face_mode=all&face_shape=circumscribed&person_ids=&mask_pending=true'
                with urllib.request.urlopen(reference_url,timeout=30) as r:reference_bytes=r.read()
                (OUT/'custom-frame65-reference.jpg').write_bytes(reference_bytes)
                expected=np.asarray(Image.open(io.BytesIO(reference_bytes)).convert('RGB')).astype(float)
                observed=np.asarray(Image.open(OUT/'custom_uncached_jpeg-final.png').convert('RGB')).astype(float)
                report['final_custom_frame65_pixel_mae']=float(np.abs(expected-observed).mean())
                assert report['final_custom_frame65_pixel_mae']<2,'visible custom final frame differs from real frame65 endpoint'
                report['checks'].append('visible final custom image matches fresh real frame65 JPEG (pixel MAE <2)')
                check('custom final protected center black',"(()=>{const s=__sample();return s.center&&s.center.slice(0,3).every(x=>x<25)})()")
                # Reject clicks attributed to an old displayed frame using the actual viewer handler.
                js("samCapabilities={...samCapabilities,available:true};samWarmup={...samWarmup,state:'ready'};window.__oldPrompts=JSON.stringify(settings.samPrompts);window.__oldSamCount=__fetches.filter(x=>x.url.includes('/api/sam/preview')).length;samDisplayed=JSON.stringify([selectedSegment.id,64,generation]);const r=preview.getBoundingClientRect();$('#viewer').dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2}))")
                check('old displayed frame click rejected without prompt mutation or SAM request',"JSON.stringify(settings.samPrompts)===__oldPrompts&&__fetches.filter(x=>x.url.includes('/api/sam/preview')).length===__oldSamCount")
                report['stale_click_status']=js("$('#samStatus').textContent")
                check('stale click reaches displayed-frame guard',"$('#samStatus').textContent.includes('正在定位本帧')")
                cross=drag('cross_raw_to_custom',135,10,2000)
                check('cross-segment custom protected frame never raw visible',"__lastDrag.samples.filter(s=>s.custom&&s.ready).every(s=>s.sourceHidden)")
                check('cross-segment custom visible media has protected center',"__lastDrag.samples.filter(s=>s.custom&&s.ready&&s.display&&s.center).every(s=>s.center.slice(0,3).every(x=>x<25))")
                check('cross final custom frame ownership','samDisplayed===JSON.stringify([selectedSegment.id,10,generation])')
                # Keyboard cut movement is production behavior; synthetic pointer capture already covered timeline scrub.
                js("window.__cutsBefore=segments.map(s=>[s.start,s.end]);document.querySelector('.cut-marker').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))")
                check('cut keyboard movement commits one frame','segments[0].end===76&&segments[1].start===76')
                js("$('#undoSplit').click()")
                check('undo restores original cut and analysis identity',"segments[0].end===75&&segments[1].start===75&&segments[0].analysisId==='controlled-custom'")
                report['browser_errors']=js('__errors');check('no browser errors','__errors.length===0')
                report['passed']=True
            except BaseException:
                report['passed']=False;report['error']=traceback.format_exc();print(report['error'],flush=True)
                try:report['failure_state']=js('__sample()');report['browser_errors']=js('__errors')
                except Exception:pass
            finally:
                report['requests']=js('__fetches');(OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');window.destroy()
        webview.start(run,gui='edgechromium',debug=False)
    finally:
        proc.terminate()
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        log.close();report['cleanup']={'owned_server_pid':proc.pid,'exit':proc.returncode,'webview_destroyed':True}
        report['html_unchanged']=hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest()==actual
        (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report.get('passed'),report.get('error')

INSTRUMENT=r"""(()=>{
window.__errors=[];window.__fetches=[];window.__timelineCalls=0;
addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));
const rt=renderTimeline;renderTimeline=function(){__timelineCalls++;return rt.apply(this,arguments)};
const rf=fetch;fetch=async function(url,options){const rec={url:String(url),at:performance.now(),aborted:false};__fetches.push(rec);options?.signal?.addEventListener('abort',()=>{rec.aborted=true;rec.abortAt=performance.now()},{once:true});try{const r=await rf.apply(this,arguments);rec.status=r.status;rec.headersAt=performance.now();const rb=r.blob.bind(r);r.blob=async()=>{try{return await rb()}finally{rec.bodyEnd=performance.now()}};return r}catch(e){rec.error=e.name;rec.bodyEnd=performance.now();throw e}};
const capture=new Set();timelinePlane.setPointerCapture=id=>capture.add(id);timelinePlane.releasePointerCapture=id=>capture.delete(id);timelinePlane.hasPointerCapture=id=>capture.has(id);
window.__sample=()=>{let el=[protectedVideo,playbackCanvas,preview,source].find(e=>!e.hidden),hash='',center=null;try{if(el){const c=document.createElement('canvas');c.width=32;c.height=24;const x=c.getContext('2d');x.drawImage(el,0,0,32,24);const d=x.getImageData(0,0,32,24).data;let h=2166136261;for(let i=0;i<d.length;i+=4)h=Math.imul(h^d[i],16777619);hash=String(h>>>0);center=Array.from(x.getImageData(16,12,1,1).data)}}catch(e){}return {now:performance.now(),frame:globalFrame,slider:Number($('#frameSlider').value),seg:selectedSegment?.id,segStart:selectedSegment?.start,custom:settings.mode==='custom',ready:analysisReady,display:el?.id,hash,center,sourceHidden:source.hidden,decodedSourceFrame,samDisplayed,sourceTime:source.currentTime,protectedTime:protectedVideo.currentTime}};
window.__drag=async(name,start,end,duration)=>{const samples=[],begin=performance.now(),calls=__timelineCalls,requestStart=__fetches.length,id=941;let events=0;const event=(type,frame)=>{const r=timelinePlane.getBoundingClientRect();timelinePlane.dispatchEvent(new PointerEvent(type,{bubbles:true,cancelable:true,pointerId:id,pointerType:'mouse',isPrimary:true,button:0,buttons:type==='pointerup'?0:1,clientX:r.left+(frame+.2)/media.frames*timelineWidth(),clientY:r.top+10}));events++};event('pointerdown',start);while(performance.now()-begin<duration){const p=Math.min(1,(performance.now()-begin)/duration);event('pointermove',Math.round(start+(end-start)*p));samples.push(__sample());await new Promise(r=>setTimeout(r,30))}const upAt=performance.now();const heldAborts=__fetches.slice(requestStart).filter(r=>r.url.includes('/api/preview/')&&r.abortAt<upAt).length;event('pointerup',end);const requests=__fetches.slice(requestStart).filter(r=>r.url.includes('/api/preview/'));window.__lastDrag={name,start,end,begin,upAt,preview_aborted_during_held:heldAborts,elapsed_ms:performance.now()-begin,events,renderTimeline_calls:__timelineCalls-calls,preview_requests:requests.length,preview_aborted:requests.filter(r=>r.aborted).length,distinct_visible_during:new Set(samples.filter(s=>s.hash).map(s=>s.hash)).size,samples};window.__dragDone=true};
})()"""
if __name__=='__main__':main()
