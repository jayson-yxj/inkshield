"""Verify running desktop/EXE identity APIs using a short locally supplied clip.

Usage: python verify_identity_packaged.py DESKTOP_STATE --input real5.mp4 --require-frozen
Writes only its own fixture, exports, and JSON report to --output (default runtime/identity-verification).
"""
import argparse
import base64
import json
import time
from pathlib import Path
import cv2
import httpx
import numpy as np


def decode(path):
    cap=cv2.VideoCapture(str(path)); frames=[]
    try:
        while True:
            ok, frame=cap.read()
            if not ok: break
            frames.append(frame)
    finally: cap.release()
    assert frames, f'No decoded frames: {path}'
    return frames


def wait(client, job, desired):
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        response=client.get('/api/status/'+job);response.raise_for_status();status=response.json()
        assert status['state']!='error',status
        if status['state']==desired:return status
        time.sleep(.1)
    raise AssertionError(f'Timed out waiting for {job}: {desired}')


def main():
    p=argparse.ArgumentParser();p.add_argument('state');p.add_argument('--input',required=True)
    p.add_argument('--frames',type=int,default=30);p.add_argument('--start-frame',type=int,default=0)
    p.add_argument('--require-frozen',action='store_true');p.add_argument('--output',default='runtime/identity-verification')
    p.add_argument('--expected-targets',nargs='+',default=['face','plate'])
    args=p.parse_args();assert 5<=args.frames<=60
    state=json.loads(Path(args.state).read_text(encoding='utf-8'))
    if args.require_frozen: assert state['frozen'],state
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    fixture=out/'face-identity-short.mp4'
    cap=cv2.VideoCapture(str(Path(args.input).resolve()));assert cap.isOpened(),args.input
    fps=cap.get(cv2.CAP_PROP_FPS);assert fps>0
    for _ in range(args.start_frame):assert cap.grab()
    ok,frame=cap.read();assert ok
    height,width=frame.shape[:2]
    writer=cv2.VideoWriter(str(fixture),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height));assert writer.isOpened()
    count=0
    try:
        while ok and count<args.frames:
            writer.write(frame);count+=1;ok,frame=cap.read()
    finally:writer.release();cap.release()
    assert count>=5
    originals=decode(fixture)
    report={'frozen':state.get('frozen'), 'url':state['url'],'fixture':str(fixture),'frames':count,'cases':[]}
    with httpx.Client(base_url=state['url'],timeout=180,trust_env=False) as c:
        health=c.get('/api/health');health.raise_for_status();health=health.json()
        assert health['model_ready'] and health['targets']==args.expected_targets,health
        assert health['class_id']==16 and health['recognition_model']=='w600k_mbf.onnx',health
        with fixture.open('rb') as stream:r=c.post('/api/analyze',files={'video':('identity.mp4',stream,'video/mp4')})
        r.raise_for_status();job=r.json()['analysis_id'];status=wait(c,job,'ready')
        r=c.get('/api/playback/'+job);r.raise_for_status();playback=r.json()
        assert playback['frames']==count and len(playback['shapes'])==count
        people=playback['people'];assert people,'Fixture did not enroll anyone; use --start-frame on a clear face segment'
        assert status['people']==people and status['pending_count']==playback['pending_count']
        valid={person['id'] for person in people}
        assigned={person['id']:0 for person in people};pending=0
        for person in people:
            thumb=cv2.imdecode(np.frombuffer(base64.b64decode(person['thumbnail'],validate=True),np.uint8),cv2.IMREAD_COLOR)
            assert thumb is not None and thumb.shape[:2]==(112,112)
        for shapes in playback['shapes']:
            for shape in shapes:
                assert len(shape)==8 and shape[6] in (16,21),shape
                if shape[6]==21:assert shape[7] is None
                elif shape[7] is None:pending+=1
                else: assert shape[7] in valid;assigned[shape[7]]+=1
        assert pending==playback['pending_count'] and pending>0
        assert all(person['count']==assigned[person['id']] for person in people)
        cache=Path(state['data_dir'])/'runtime'/job/'detections.json'
        if cache.is_file():
            saved=json.loads(cache.read_text(encoding='utf-8'))
            assert len(saved['detections'])==count and len(saved['face_ids'])==count
            assert all(len(boxes)==len(ids) for boxes,ids in zip(saved['detections'],saved['face_ids']))
            assert all(len(box)==6 for boxes in saved['detections'] for box in boxes)
        for options in ({'face_mode':'bad'},{'person_ids':'0'},{'person_ids':str(max(valid)+1)},{'person_ids':'1,'},{'target':'head'},{'target':'eyes'}):
            assert c.get('/api/preview/'+job,params=options).status_code==422,options
            assert c.post('/api/export/'+job,data=options).status_code==422,options
        assert all(s[0]=='ellipse' for shapes in playback['shapes'] for s in shapes if s[6]==16)
        cases=[('empty_targets',{'target':''}),('all',{'face_mode':'all','mask_pending':'false'}),
               ('inscribed',{'face_mode':'all','face_shape':'inscribed'}),
               ('none',{'face_mode':'selected','person_ids':'','mask_pending':'false'}),
               ('pending',{'face_mode':'selected','person_ids':'','mask_pending':'true'}),
               ('person',{'face_mode':'selected','person_ids':str(min(valid)),'mask_pending':'false'})]
        for name,options in cases:
            options={'target':'face','style':'black','strength':'100',**options}
            r=c.post('/api/export/'+job,data={**options,'muted':'true'});r.raise_for_status()
            exported=wait(c,r.json()['job_id'],'done');assert exported['inference_ms']==0
            r=c.get(exported['download']);r.raise_for_status();path=out/(name+'.mp4');path.write_bytes(r.content)
            frames=decode(path);assert len(frames)==count
            dark_checks=0;unmasked_checks=0
            for index,(source,result,shapes) in enumerate(zip(originals,frames,playback['shapes'])):
                for shape in shapes:
                    kind,cx,cy,rx,ry,angle,classid,pid=shape
                    if classid!=16:continue
                    masked=name in ('all','inscribed') or (name=='pending' and pid is None) or (name=='person' and pid==min(valid))
                    x,y=int(round(cx)),int(round(cy))
                    if not 2<=x<width-2 or not 2<=y<height-2:continue
                    patch=result[y-1:y+2,x-1:x+2];original=source[y-1:y+2,x-1:x+2]
                    if masked:
                        assert float(patch.mean())<12,(name,index,pid,float(patch.mean()));dark_checks+=1
                    elif float(original.mean())>20:
                        # A different selected face could geometrically overlap this one.
                        overlap=any(s is not shape and s[6]==16 and abs(x-s[1])<s[3] and abs(y-s[2])<s[4] and
                                    (name in ('all','inscribed') or (name=='pending' and s[7] is None) or (name=='person' and s[7]==min(valid))) for s in shapes)
                        if not overlap:assert float(patch.mean())>12,(name,index,pid);unmasked_checks+=1
            preview_index=next(i for i,shapes in enumerate(playback['shapes']) if any(s[6]==16 and s[7] is not None for s in shapes))
            r=c.get('/api/preview/'+job,params={**options,'frame':preview_index});r.raise_for_status()
            preview=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
            difference=float(np.abs(preview.astype(float)-frames[preview_index].astype(float)).mean())
            assert difference<12,(name,difference)
            report['cases'].append({'name':name,'export_frames':len(frames),'masked_center_checks':dark_checks,'unmasked_center_checks':unmasked_checks,'preview_export_mae':difference})
        outer=decode(out/'all.mp4');inner=decode(out/'inscribed.mp4')
        assert sum(np.count_nonzero(np.max(f,axis=2)<12) for f in outer)>sum(np.count_nonzero(np.max(f,axis=2)<12) for f in inner), 'Inscribed export did not shrink mask'
        for style in ('boxblur','horizontal','vertical'):
            options={'target':'face','style':style,'strength':'80','muted':'true'}
            r=c.post('/api/export/'+job,data=options);r.raise_for_status()
            exported=wait(c,r.json()['job_id'],'done')
            path=out/(style+'.mp4');r=c.get(exported['download']);r.raise_for_status();path.write_bytes(r.content)
            frames=decode(path);assert len(frames)==count
            r=c.get('/api/preview/'+job,params={**options,'frame':10});r.raise_for_status()
            preview=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
            difference=float(np.abs(preview.astype(float)-frames[10].astype(float)).mean());assert difference<12
            assert float(np.abs(frames[10].astype(float)-originals[10].astype(float)).mean())>.1
            report['cases'].append({'name':style,'export_frames':len(frames),'preview_export_mae':difference})
        assert c.get('/api/playback/'+job).json()==playback,'Cached analysis mutated across selection changes'
        report.update(analysis_id=job,people=[{'id':p['id'],'count':p['count']} for p in people],pending_count=pending,health=health,plate_detections=sum(s[6]==21 for f in playback['shapes'] for s in f))
        report['limits']='Face identity is appearance grouping, not human-validated accuracy. This fixture does not establish audio or plate coverage unless detections/source audio are separately exercised.'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2));print('IDENTITY DESKTOP/PACKAGED FLOW PASS')

if __name__=='__main__':main()
