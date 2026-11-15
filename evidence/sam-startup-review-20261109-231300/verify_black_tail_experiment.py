"""One actual SAM propagation attempt: real frame0 then four black frames. Not target-exit ground truth."""
import argparse,base64,json,time,urllib.request,urllib.error,uuid
from pathlib import Path
import cv2,numpy as np
OUT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--base',default='http://127.0.0.1:50164');p.add_argument('--source',type=Path,default=Path(r'C:\Users\36301/Desktop/5.mp4'));a=p.parse_args()
if not a.execute:p.error('Requires freeze and exclusive inference slot')
report={'scope':__doc__,'frames':5}
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(path,data=None,ct='application/json'):
    req=urllib.request.Request(a.base+path,data=data,headers={'Content-Type':ct})
    try:
        with opener.open(req,timeout=600) as r:return r.status,r.read()
    except urllib.error.HTTPError as e:return e.code,e.read()
try:
    s,b=call('/api/sam/warmup');warm=json.loads(b);assert s==200 and warm['state']=='ready'
    device=warm['device'];report['device']=device
    cap=cv2.VideoCapture(str(a.source));ok,frame=cap.read();cap.release();assert ok
    h,w=frame.shape[:2];path=OUT/'real-first-frame-four-black.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),25,(w,h));assert writer.isOpened()
    writer.write(frame)
    for i in range(4):writer.write(np.zeros_like(frame))
    writer.release()
    boundary='BlackTail'+uuid.uuid4().hex
    data=f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="black-tail.avi"\r\nContent-Type: video/x-msvideo\r\n\r\n'.encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
    s,b=call('/api/media',data,'multipart/form-data; boundary='+boundary);media=json.loads(b);assert s==200 and media['frames']==5,media
    report['media']=media
    request={'media_id':media['media_id'],'start_frame':0,'end_frame':5,'device':device,'prompts':{'0':[{'x':646,'y':218,'label':1}]}}
    s,b=call('/api/sam/analyze',json.dumps(request).encode());submitted=json.loads(b);assert s==200,submitted
    report['submission']=submitted;deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        s,b=call(submitted['status']);status=json.loads(b)
        if status['state'] in ('ready','error'):break
        time.sleep(.25)
    assert status['state']=='ready',status
    report['status']=status;counts=[]
    for i in range(5):
        s,png=call(f"/api/sam/mask/{submitted['analysis_id']}/{i}.png");assert s==200
        mask=cv2.imdecode(np.frombuffer(png,np.uint8),cv2.IMREAD_UNCHANGED);assert mask.shape==(h,w,4)
        (OUT/f'black-tail-mask-{i}.png').write_bytes(png);counts.append(int(np.count_nonzero(mask[:,:,3])))
    report['alpha_nonzero_per_frame']=counts
    report['black_frames_empty']=[c==0 for c in counts[1:]]
    report['conclusion']='Observed mask pixels only. Black image edits are synthetic; this does not prove genuine target departure in 5.mp4.'
    report['passed']=True
except BaseException as e:
    report.update(passed=False,error=repr(e));raise
finally:
    (OUT/'black-tail-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
