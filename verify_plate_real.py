"""Actual HyperLPR positive sample through upload/cache/preview/playback/export."""
import cv2
import numpy as np
import server
from fastapi.testclient import TestClient
from verify_cached import wait
image=cv2.imdecode(np.fromfile('research/hyperlpr-sample.jpg',np.uint8),1)
assert image is not None
height,width=image.shape[:2]
width-=width%2; height-=height%2
image=image[:height,:width]
path=server.RUNTIME/'plate-real-input.mp4'
writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(width,height))
assert writer.isOpened()
for i in range(8):writer.write(image)
writer.release()
with TestClient(server.app) as client:
    with path.open('rb') as stream:
        r=client.post('/api/analyze',files={'video':('plate.mp4',stream,'video/mp4')})
    assert r.status_code==200,r.text
    job=r.json()['job_id']; status=wait(client,job,{'ready'})
    analysis=server.ANALYSES[job]
    assert status['frames']==8
    plates=[[b for b in rows if b[5]==21] for rows in analysis.boxes]
    assert all(plates),plates
    print('REAL PLATE DETECTIONS',len(plates[0]),plates[0],flush=True)
    def forbidden(*args,**kwargs):raise AssertionError('cached render called inference')
    server.get_detector=server.get_plate_detector=forbidden
    shapes=client.get('/api/playback/'+job).json()['shapes']
    assert all(any(s[-1]==21 and s[0]=='rectangle' for s in row) for row in shapes)
    for style in server.MASK_STYLES:
        r=client.get('/api/preview/'+job,params={'target':'plate','style':style})
        assert r.status_code==200,r.text
        assert cv2.imdecode(np.frombuffer(r.content,np.uint8),1) is not None
    r=client.post('/api/export/'+job,data={'target':'plate','style':'black'})
    assert r.status_code==200,r.text
    result=wait(client,r.json()['job_id'],{'done'})
    output=server.RUNTIME/r.json()['job_id']/'output.mp4'
    cap=cv2.VideoCapture(str(output)); count=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        for box in plates[count]:
            x0,y0,x1,y1=map(int,box[:4]); x0+=2;y0+=2;x1-=2;y1-=2
            assert np.max(frame[y0:y1,x0:x1])<35
        count+=1
    cap.release();assert count==8
    print('REAL PLATE E2E PASS',status['analysis_seconds'],result['export_seconds'],output,flush=True)
