"""Live API evidence. Explicit --execute required; never starts/stops the server."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--observe-only', action='store_true', help='Record warming -> ready without upload/inference')
    p.add_argument('--allow-already-ready', action='store_true', help='Explicitly waive startup transition requirement; report remains partial')
    p.add_argument('--base', default='http://127.0.0.1:50164')
    p.add_argument('--source', type=Path, default=Path(r'C:\Users\36301\Desktop\5.mp4'))
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--output', type=Path, default=OUT/'api-run')
    a = p.parse_args()
    if not a.execute:
        p.error('Prepared only. Run --execute after freeze and slot authorization.')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    report = {'base':a.base, 'source':str(a.source), 'started_at':time.time(), 'warmup_samples':[], 'code_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('desktop.py','sam_engine.py','sam_service.py','index.html')}}
    def save(name, obj):
        (out/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    def call(name, path, payload=None, content_type='application/json'):
        req = urllib.request.Request(a.base.rstrip('/')+path, data=payload, headers={'Content-Type':content_type,'Cache-Control':'no-cache'})
        started = time.perf_counter()
        try:
            with opener.open(req, timeout=a.timeout) as r: status, body = r.status,r.read()
        except urllib.error.HTTPError as e:
            status,body = e.code,e.read()
        elapsed = time.perf_counter()-started
        obj = json.loads(body)
        save(name+'-response',obj)
        report[name] = {'status':status,'wall_seconds':elapsed}
        return status,obj
    try:
        deadline=time.monotonic()+a.timeout
        saw_warming=False
        while time.monotonic()<deadline:
            try:
                status,warm=call('warmup-latest','/api/sam/warmup')
                sample={'at':time.time(),'status':status,'response':warm}
                if status==404:
                    report['warmup_samples'].append(sample)
                    save('report',report)
                    time.sleep(.2)
                    continue
                assert status==200, sample
                saw_warming |= warm.get('state')=='warming'
                report['warmup_samples'].append(sample)
                save('report',report)
                if warm.get('state')=='error': raise AssertionError(warm)
                if warm.get('state')=='ready' and (saw_warming or a.allow_already_ready): break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                report['warmup_samples'].append({'at':time.time(),'connection_error':str(e)})
                save('report',report)
            time.sleep(.2)
        else: raise AssertionError('Did not observe warming -> ready before deadline; start observer before parent restart')
        report['observed_warming_to_ready']=saw_warming
        report['ready']=warm
        device=warm['device']; assert device in ('cpu','cuda'),warm
        status,caps=call('capabilities','/api/sam/capabilities')
        assert status==200 and caps['available'] and caps['default_device']==device,caps
        assert caps['warmup']['state']=='ready' and caps['warmup']['device']==device,caps
        if a.observe_only:
            report['passed']=saw_warming
            report['scope']='startup observation only; no upload or real preview'
            return
        import cv2
        import numpy as np
        raw=a.source.read_bytes()
        report.update(source_sha256=hashlib.sha256(raw).hexdigest(),source_bytes=len(raw))
        boundary='SamStartup'+uuid.uuid4().hex
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="5.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
        status,media=call('upload','/api/media',body,'multipart/form-data; boundary='+boundary)
        assert status==200 and media['frames']==6454,media
        report['media']=media
        for frame in (0,1):
            name='first-real-preview' if frame==0 else 'new-frame-preview'
            request={'media_id':media['media_id'],'start_frame':0,'end_frame':6454,'device':device,'frame':frame,'prompts':[{'x':646,'y':218,'label':1}]}
            save(name+'-request',request)
            status,result=call(name,'/api/sam/preview',json.dumps(request).encode())
            assert status==200,result
            png=base64.b64decode(result['mask'],validate=True)
            image=cv2.imdecode(np.frombuffer(png,np.uint8),cv2.IMREAD_UNCHANGED)
            assert image is not None and image.shape==(media['height'],media['width'],4)
            selected=int(np.count_nonzero(image[:,:,3]))
            assert result['empty']==(selected==0),result
            timing=result['timing_ms']
            assert timing['model_load']==0, timing
            assert timing['encoder']>0 and result['cache_hit'] is False,timing
            assert result['seconds']>0,result
            (out/(name+'-mask.png')).write_bytes(png)
            report[name].update(seconds=result['seconds'],timing_ms=timing,cache_hit=result['cache_hit'],empty=result['empty'],alpha_nonzero=selected)
        request={k:v for k,v in request.items() if k!='frame'}
        request['prompts']={'0':[{'x':646,'y':218,'label':1}]}
        status,rejection=call('long-propagation-rejection','/api/sam/analyze',json.dumps(request).encode())
        assert status==422 and '150' in str(rejection),rejection
        report['api_checks_passed']=True
        observer=OUT/'observer-run'/'report.json'
        if not saw_warming and observer.exists():
            startup=json.loads(observer.read_text(encoding='utf-8'))
            if startup.get('passed') and startup.get('observed_warming_to_ready') and startup.get('ready')==warm and startup.get('base')==a.base and startup.get('finished_at',float('inf'))<=report['started_at']:
                report['startup_evidence']={'path':str(observer),'sha256':hashlib.sha256(observer.read_bytes()).hexdigest()}
                saw_warming=True
        report['passed']=saw_warming
        report['scope']='full 6454-frame upload; preview frame0 and frame1 only; propagation limit rejection; no full video propagation'
    except BaseException as e:
        report.update(passed=False,error=repr(e))
        raise
    finally:
        report['finished_at']=time.time();save('report',report)
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
