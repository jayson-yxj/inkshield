"""Controlled-mask acceptance of real production encoding + WebView2 playback; no SAM inference.
Run only after parent freeze: .venv-sam-build/Scripts/python ... --execute
No Win32 foreground APIs; all transport interactions are DOM clicks.
"""
from pathlib import Path
import argparse, base64, hashlib, json, os, subprocess, sys, time, traceback, urllib.request
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))

def server_mode():
    os.environ['INKSHIELD_DATA_DIR']=str(OUT/'isolated-data')
    import server, sam_service, numpy as np, uvicorn, socket
    # Controlled already-cached analyses require no predictor load or inference.
    sam_service.WARMUP_STATE.update(state='ready',device='cpu',error=None)
    src=OUT/'source-audio.mp4'
    masks=[]
    for i in range(75):
        mask=np.zeros((240,320),np.uint8);mask[65:175,105:215]=1;mask.flags.writeable=False;masks.append(mask)
    for name,start,count,custom in [('controlled-custom',0,75,True),('controlled-auto',75,75,False)]:
        server.ANALYSES[name]=server.Analysis(input_path=src,boxes=tuple(() for _ in range(count)),width=320,height=240,fps=25,start_frame=start,face_ids=tuple(() for _ in range(count)),custom_masks=tuple(masks) if custom else (),sam_device='cpu' if custom else None)
        server.JOBS[name]={'state':'ready','kind':'analyze','frames':count,'fps':25,'width':320,'height':240,'start_frame':start,'end_frame':start+count}
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    (OUT/'service.json').write_text(json.dumps({'pid':os.getpid(),'url':f'http://127.0.0.1:{port}/'}),encoding='utf-8')
    uvicorn.Server(uvicorn.Config(server.app,log_level='warning')).run(sockets=[sock])

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--server',action='store_true');a=p.parse_args()
    if a.server:return server_mode()
    if not a.execute:p.error('Requires parent freeze and execution signal')
    import imageio_ffmpeg
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-nostdin','-f','lavfi','-i','testsrc2=size=320x240:rate=25:duration=6','-f','lavfi','-i','sine=frequency=660:sample_rate=48000:duration=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-shortest',str(OUT/'source-audio.mp4')]
    with (OUT/'fixture.log').open('w') as log: subprocess.run(command,stdout=log,stderr=log,check=True)
    report={'scope':'Controlled immutable synthetic masks; real production endpoint encoder and actual Windows WebView2; no SAM quality claim; DOM interactions only','checks':[],'hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['index.html','server.py','preview_video.py','sam_service.py'] if (ROOT/n).exists()}}
    real_python=getattr(sys,'_base_executable',sys.executable)
    # Venv Windows redirector spawns a second PID; use real executable with venv site path.
    child_env=os.environ.copy();child_env['PYTHONPATH']=os.pathsep.join(sys.path)
    log=(OUT/'server.log').open('w');proc=subprocess.Popen([real_python,str(Path(__file__)),'--server'],cwd=ROOT,stdout=log,stderr=log,env=child_env)
    report['owned_server_pid']=proc.pid
    window=None
    try:
        deadline=time.monotonic()+30
        while True:
            assert proc.poll() is None,'isolated service exited'
            try:
                state=json.loads((OUT/'service.json').read_text(encoding='utf-8'))
                if state['pid']==proc.pid:
                    with urllib.request.urlopen(state['url'],timeout=1) as r: report['served_html_sha256']=hashlib.sha256(r.read()).hexdigest()
                    break
            except Exception:pass
            assert time.monotonic()<deadline,'isolated service startup timed out';time.sleep(.1)
        report['service']=state
        import webview
        window=webview.create_window('Inkshield smooth custom playback acceptance',state['url'],width=1420,height=860)
        def run():
            def js(code):return window.evaluate_js(code)
            def wait(expr,timeout=45):
                end=time.monotonic()+timeout
                while time.monotonic()<end:
                    value=js(expr)
                    if value:return value
                    time.sleep(.08)
                raise AssertionError('Timeout '+expr+'; '+str(js("({playing,startingPlayback,globalFrame,status:$('#statusText').textContent,note:$('#playbackNote').textContent,feedback:$('#previewFeedback').textContent})")))
            def check(name,expr):
                value=js(expr);assert value,name+' '+str(value)
                report['checks'].append(name);print('PASS '+name,flush=True)
            def snapshot(name):
                report[name]=js("({playing,startingPlayback,globalFrame,source:{time:source.currentTime,paused:source.paused,muted:source.muted},videos:Array.from(document.querySelectorAll('video')).map(v=>({id:v.id,time:v.currentTime,paused:v.paused,muted:v.muted,ready:v.readyState,width:v.videoWidth,height:v.videoHeight,src:v.currentSrc,hidden:v.hidden,error:v.error?.message,quality:v.getVideoPlaybackQuality?.()})),callbacks:__frames.slice(-200),requests:__requests.slice()})")
            try:
                wait("typeof samCapabilities!=='undefined'&&!!samCapabilities&&document.readyState==='complete'",60)
                js("window.__errors=[];window.__requests=[];window.__frames=[];addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));window.__realFetch=fetch;fetch=async function(url,options){const r={url:String(url),method:options?.method||'GET',at:performance.now()};__requests.push(r);const response=await __realFetch.apply(this,arguments);r.http=response.status;return response};window.__rvfc=HTMLVideoElement.prototype.requestVideoFrameCallback;HTMLVideoElement.prototype.requestVideoFrameCallback=function(callback){const v=this;return __rvfc.call(v,(now,m)=>{__frames.push({id:v.id,now,time:m.mediaTime,presented:m.presentedFrames});return callback(now,m)})}")
                data=base64.b64encode((OUT/'source-audio.mp4').read_bytes()).decode('ascii')
                js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0))],'controlled-6s-audio.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
                wait('!!media&&!importing&&source.readyState>=2&&clipSelected')
                check('actual 150-frame six-second audio fixture imported','media.frames===150&&media.fps===25')
                # Populate analysis references only; production loader validates real API geometry.
                js("(()=>{const left=makeSegment(0,75),right=makeSegment(75,150);left.settings.mode='custom';left.settings.targets=['custom'];left.settings.style='black';left.settings.samPrompts={'0':[{x:160,y:120,label:1}]};left.analysisId='controlled-custom';left.analysisReady=true;left.status='已分析';right.settings.mode='automatic';right.analysisId='controlled-auto';right.analysisReady=true;right.status='已分析';segments=[left,right];globalFrame=0;selectSegment(left,false)})()")
                wait('!!playback&&!$("#playPause").disabled')
                js("window.__playingRequestStart=__requests.length;$('#playPause').click()")
                wait('playing&&!startingPlayback')
                wait("__frames.filter(f=>f.id!=='source').length>=50",30)
                snapshot('playing_sample')
                check('at least fifty actual decoded frame callbacks span two seconds',"(()=>{const f=__frames.filter(f=>f.id==='protectedPlayback');return f.length>=50&&f.at(-1).time-f[0].time>=1.9&&f.at(-1).now-f[0].now>=1700})()")
                check('decoded protected video has black protected center',"(()=>{const c=document.createElement('canvas');c.width=320;c.height=240;const x=c.getContext('2d');x.drawImage(document.getElementById('protectedPlayback'),0,0);const p=x.getImageData(160,120,1,1).data;window.__protectedPixel=Array.from(p);return p[0]<20&&p[1]<20&&p[2]<20})()")
                report['protected_pixel']=js('__protectedPixel')
                asset_url=js("document.getElementById('protectedPlayback').currentSrc")
                with urllib.request.urlopen(asset_url,timeout=30) as response: (OUT/'actual-protected-playback.mp4').write_bytes(response.read())
                import av
                with av.open(str(OUT/'actual-protected-playback.mp4')) as container:
                    report['encoded_streams']=[{'type':s.type,'codec':s.codec_context.name,'duration':float(s.duration*s.time_base) if s.duration else None} for s in container.streams]
                    assert container.streams.video[0].codec_context.name=='h264'
                    assert container.streams.audio[0].codec_context.name=='aac'
                    report['decoded_video_frames']=sum(1 for _ in container.decode(video=0))
                with av.open(str(OUT/'actual-protected-playback.mp4')) as container:
                    report['decoded_audio_samples']=sum(f.samples for f in container.decode(audio=0))
                assert report['decoded_video_frames']==75 and report['decoded_audio_samples']>=140000
                report['checks'].append('protected H264/AAC asset decodes all 75 video frames and three seconds audio')
                check('dedicated video decoder advances at least half second',"Array.from(document.querySelectorAll('video')).some(v=>v!==source&&!v.paused&&v.readyState>=2&&v.currentTime>.5&&v.videoWidth===320&&v.videoHeight===240)")
                check('source paused while protected video owns playback','source.paused')
                check('no JPEG per-frame fetch during running protected playback',"!__requests.slice(__playingRequestStart).some(r=>r.url.includes('/api/preview/'))")
                js("$('#previewMute').click()")
                check('mute control updates dedicated video',"Array.from(document.querySelectorAll('video')).filter(v=>v!==source).every(v=>v.muted===previewMuted)")
                js("$('#previewMute').click();$('#playPause').click()")
                wait('!playing&&!startingPlayback')
                paused=js("Array.from(document.querySelectorAll('video')).find(v=>v!==source).currentTime")
                time.sleep(.35)
                check('pause stops decoder clock',"Math.abs(Array.from(document.querySelectorAll('video')).find(v=>v!==source).currentTime-"+str(paused)+")<.08")
                js("$('#playPause').click()")
                wait('playing&&!startingPlayback')
                wait("Array.from(document.querySelectorAll('video')).find(v=>v!==source).currentTime>"+str(paused+.25))
                check('resume keeps decoded protected stream',"__requests.filter(r=>r.url.includes('/api/custom-playback/')&&r.method==='POST').length===1")
                js("$('#playPause').click();seekGlobal(25,0)")
                time.sleep(.4)
                js("$('#playPause').click()")
                wait('playing&&!startingPlayback')
                check('seek restarts at segment-local one second',"Array.from(document.querySelectorAll('video')).find(v=>v!==source).currentTime>=1&&Array.from(document.querySelectorAll('video')).find(v=>v!==source).currentTime<1.8")
                js("$('#playPause').click()")
                snapshot('transport_sample')
                # Style handler is exercised through actual UI click.
                js("document.querySelector('.seg[data-group=style] button[data-value=mosaic]').click();$('#playPause').click()")
                wait('playing&&!startingPlayback')
                check('style change requests a distinct protected asset',"__requests.filter(r=>r.url.includes('/api/custom-playback/')&&r.method==='POST').length>=2")
                js("$('#playPause').click();seekGlobal(0,0);deselectClip();$('#playPause').click()")
                wait('playing&&!startingPlayback')
                wait('globalFrame>=85',30)
                snapshot('continuous_auto_boundary')
                check('continuous custom to automatic boundary advances source decoder','continuousMode&&globalFrame>=85&&!source.paused')
                wait('!playing&&!startingPlayback',20)
                # Reconfigure only fixture second segment as unanalysed, exercise same production boundary.
                js("segments[1].analysisReady=false;segments[1].analysisId='';segments[1].playback=null;globalFrame=0;$('#playPause').click()")
                wait('playing&&!startingPlayback')
                wait('globalFrame>=85',30)
                snapshot('continuous_unanalyzed_boundary')
                check('continuous custom to unanalysed boundary advances safely','continuousMode&&globalFrame>=85&&!source.paused')
                js("$('#playPause').click()")
                check('no browser errors','__errors.length===0')
                report['passed']=True
            except BaseException:
                report['passed']=False;report['error']=traceback.format_exc();print(report['error'],flush=True)
                try:snapshot('failure_state');report['browser_errors']=js('__errors')
                except Exception:pass
            finally:
                (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                window.destroy()
        webview.start(run,gui='edgechromium',debug=False)
    finally:
        proc.terminate()
        try:proc.wait(timeout=15)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        log.close();report['cleanup']={'owned_server_exit':proc.returncode,'webview_window_destroyed':True}
        (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert report.get('passed'),report.get('error')
if __name__=='__main__':main()
