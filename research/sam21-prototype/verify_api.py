"""End-to-end real SAM service acceptance; caller owns service lifecycle."""
import argparse,json,time
from pathlib import Path
import cv2,httpx,numpy as np
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--input',required=True);p.add_argument('--x',type=float,required=True);p.add_argument('--y',type=float,required=True);p.add_argument('--output',default='runtime/acceptance');a=p.parse_args()
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
def wait(c,jid):
    start=time.monotonic()
    while time.monotonic()-start<900:
        r=c.get('/api/job/'+jid);r.raise_for_status();j=r.json()
        if j['state']=='error':raise AssertionError(j)
        if j['state']=='done':return j
        time.sleep(.25)
    raise AssertionError('SAM任务超过15分钟')
with httpx.Client(base_url=a.url,timeout=120,trust_env=False) as c:
    with open(a.input,'rb') as f:r=c.post('/api/import',files={'video':('test.mp4',f,'video/mp4')})
    r.raise_for_status();s=r.json();sid=s['id'];report={'session':s,'cases':[]}
    assert c.post('/api/export/'+sid,json={}).status_code==409
    assert c.post('/api/segment/'+sid,json={'prompts':{}}).status_code==422
    prompts={'0':[{'x':a.x,'y':a.y,'label':1}]}
    r=c.post('/api/segment/'+sid,json={'prompts':prompts});r.raise_for_status();seg=wait(c,r.json()['job_id']);report['segment']=seg
    areas=[]
    for frame in range(s['frames']):
        r=c.get(f'/api/mask/{sid}/{frame}.png');r.raise_for_status();mask=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_UNCHANGED)
        assert mask.shape==(s['height'],s['width'],4);areas.append(int(np.count_nonzero(mask[:,:,3])))
    assert areas[0]>0;report['areas']=areas
    for style in ('black','mosaic','blur'):
        r=c.post('/api/export/'+sid,json={'style':style,'strength':80,'padding':6});r.raise_for_status();job=wait(c,r.json()['job_id'])
        r=c.get(job['download']);r.raise_for_status();path=out/(style+'.mp4');path.write_bytes(r.content)
        cap=cv2.VideoCapture(str(path));count=0;first=None
        while True:
            ok,f=cap.read()
            if not ok:break
            if first is None:first=f
            count+=1
        cap.release();assert count==s['frames']
        r=c.get(f'/api/preview/{sid}/0.jpg',params={'style':style,'strength':80,'padding':6});r.raise_for_status();preview=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
        mae=float(abs(preview.astype(float)-first.astype(float)).mean());assert mae<12
        report['cases'].append({'style':style,'decoded_frames':count,'preview_export_mae':mae})
    # Correction and bidirectional anchor away from frame zero.
    anchor=s['frames']//2
    prompts={str(anchor):[{'x':a.x,'y':a.y,'label':1},{'x':0,'y':0,'label':0}]}
    r=c.post('/api/segment/'+sid,json={'prompts':prompts});r.raise_for_status();correction=wait(c,r.json()['job_id']);report['correction']=correction
    for frame in (0,anchor,s['frames']-1):assert c.get(f'/api/mask/{sid}/{frame}.png').status_code==200
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
