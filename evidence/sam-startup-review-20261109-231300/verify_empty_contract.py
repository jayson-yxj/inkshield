"""Controlled fixture only: no model inference, no claims about real target exit."""
import argparse
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:p.error('Requires freeze/slot authorization')
    import server,sam_service
    from fastapi.testclient import TestClient
    caps={'available':True,'devices':[{'id':'cpu','available':True}],'default_device':'cpu'}
    class ImmediateThread:
        def __init__(self,target,args,**kw): self.target,self.args=target,args
        def start(self): self.target(*self.args)
    class Engine:
        def preview(self,rgb,points,key):return np.zeros(rgb.shape[:2],np.uint8),{'seconds':.1,'cache_hit':False}
        def segment(self,directory,prompts,count,progress):
            masks={i:np.zeros((48,64),np.uint8) for i in range(count)}
            masks[0][10:20,10:20]=1
            return masks,{'fixture':True,'total_seconds':.1}
    report={'scope':'Controlled mocked-engine fixture; proves empty-mask API/storage contract only; no actual SAM inference or real-video exit claim'}
    try:
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);src=td/'fixture.avi';runtime=td/'runtime';runtime.mkdir()
            writer=cv2.VideoWriter(str(src),cv2.VideoWriter_fourcc(*'MJPG'),25,(64,48))
            assert writer.isOpened()
            for i in range(3):writer.write(np.full((48,64,3),120,np.uint8))
            writer.release()
            media_id='evidence-empty-fixture';server.MEDIA[media_id]={'input_path':src,'frames':3,'fps':25,'width':64,'height':48}
            client=TestClient(server.app)
            request={'media_id':media_id,'start_frame':0,'end_frame':3,'device':'cpu','frame':0,'prompts':[{'x':20,'y':20,'label':1}]}
            with patch.object(server,'RUNTIME',runtime),patch('sam_engine.capabilities',return_value=caps),patch('sam_service.engine',return_value=Engine()),patch('sam_service.threading',type('FixtureThreads',(),{'Thread':ImmediateThread})):
                r=client.post('/api/sam/preview',json=request);assert r.status_code==200,r.text
                data=r.json();png=cv2.imdecode(np.frombuffer(base64.b64decode(data['mask']),np.uint8),cv2.IMREAD_UNCHANGED)
                assert data['empty'] is True and png.shape==(48,64,4) and not np.any(png[:,:,3])
                report['empty_preview']={'http':200,'empty':True,'alpha_nonzero':0,'lock_released':not sam_service.SAM_LOCK.locked()}
                request.pop('frame');request['prompts']={'0':request['prompts']}
                r=client.post('/api/sam/analyze',json=request);assert r.status_code==200,r.text
                job=r.json()['job_id'];status=client.get('/api/status/'+job).json();assert status['state']=='ready',status
                counts=[]
                for frame in range(3):
                    r=client.get(f'/api/sam/mask/{job}/{frame}.png');assert r.status_code==200
                    image=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_UNCHANGED);counts.append(int(np.count_nonzero(image[:,:,3])))
                assert counts==[100,0,0],counts
                assert not sam_service.SAM_LOCK.locked()
                report['propagation']={'state':status['state'],'alpha_nonzero_per_frame':counts,'immutable':[not m.flags.writeable for m in server.ANALYSES[job].custom_masks]}
                assert all(report['propagation']['immutable'])
                original=np.full((48,64,3),120,np.uint8);actual=original.copy();sam_service.apply_custom(actual,np.zeros((48,64),np.uint8),68,'black');assert np.array_equal(actual,original)
                report['empty_compositor_preserves_frame']=True
                exported=client.post('/api/export/'+job,data={'target':'custom','style':'black','muted':'true'})
                assert exported.status_code==200,exported.text
                export_job=exported.json()['job_id']
                import time
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    export_status=client.get('/api/status/'+export_job).json()
                    if export_status['state'] in ('done','error'):break
                    time.sleep(.1)
                assert export_status['state']=='done',export_status
                encoded=client.get('/api/download/'+export_job);assert encoded.status_code==200
                output=Path(__file__).resolve().parent/'empty-fixture-real-export.mp4';output.write_bytes(encoded.content)
                cap=cv2.VideoCapture(str(output));decoded=[]
                while True:
                    ok,frame=cap.read()
                    if not ok:break
                    decoded.append(frame)
                cap.release();assert len(decoded)==3,len(decoded)
                maes=[float(np.mean(np.abs(f.astype(np.float32)-120))) for f in decoded]
                assert all(f.shape==(48,64,3) for f in decoded)
                assert maes[1]<8 and maes[2]<8,maes
                assert float(decoded[0][15,15].mean())<30
                report['real_export']={'state':'done','bytes':len(encoded.content),'decoded_frames':len(decoded),'shape':[48,64,3],'source_constant':120,'frame_mae_to_source':maes,'empty_frame_mae_limit':8,'first_mask_center_mean':float(decoded[0][15,15].mean()),'path':str(output),'scope':'Official export/writer and actual MP4 decode; masks supplied by controlled engine fixture'}
            report['passed']=True
    except BaseException as e:
        report.update(passed=False,error=repr(e));raise
    finally:
        (Path(__file__).resolve().parent/'empty-fixture-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
