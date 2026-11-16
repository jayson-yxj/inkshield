"""SAM contracts without loading optional torch/model assets."""
import base64
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from inkshield import server
from inkshield import sam_service


CAPS = {"available":True,"devices":[{"id":"cpu","available":True},{"id":"cuda","available":False}],"default_device":"cpu"}


class SamIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'input.avi'
        writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*'MJPG'),25,(64,48))
        for i in range(3):
            writer.write(np.random.default_rng(i).integers(20,255,(48,64,3),dtype=np.uint8))
        writer.release()
        self.media='sam-test-media'
        server.MEDIA[self.media]={"input_path":self.path,"frames":3,"fps":25,"width":64,"height":48}
        self.client=TestClient(server.app)
        self.request={"media_id":self.media,"start_frame":0,"end_frame":3,"frame":0,"prompts":[{"x":20,"y":20,"label":1}],"device":"cpu"}

    def tearDown(self):
        server.MEDIA.pop(self.media,None)
        server.ANALYSES.pop('sam-test-analysis',None)
        server.JOBS.pop('sam-test-analysis',None)
        self.tmp.cleanup()

    def analysis(self,masks=True):
        mask=np.zeros((48,64),dtype=np.uint8);mask[15:25,20:30]=1
        mask=np.frombuffer(mask.tobytes(),dtype=np.uint8).reshape(mask.shape)
        a=server.Analysis(self.path,((),(),()),64,48,25,face_ids=((),(),()),custom_masks=(mask,mask,mask) if masks else (),sam_device='cpu' if masks else None)
        server.new_job('sam-test-analysis','analysis')
        server.update('sam-test-analysis',state='ready')
        server.ANALYSES['sam-test-analysis']=a
        return a

    def test_validation_finite_positive_and_original_bounds(self):
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS):
            for prompts in ([{"x":-1,"y":20,"label":1}],[{"x":64,"y":20,"label":1}], [{"x":20,"y":20,"label":0}], [{"x":20,"y":20,"label":True}]):
                self.assertEqual(self.client.post('/api/sam/preview',json={**self.request,'prompts':prompts}).status_code,422)
            response=self.client.post('/api/sam/preview',content=json.dumps({**self.request,'prompts':[{'x':float('nan'),'y':20,'label':1}]}),headers={'content-type':'application/json'})
            self.assertEqual(response.status_code,422)

    def test_busy_rejects_immediately(self):
        sam_service.SAM_LOCK.acquire()
        try:
            self.assertEqual(self.client.post('/api/sam/preview',json=self.request).status_code,429)
        finally:
            sam_service.SAM_LOCK.release()

    def test_preview_png_and_cache_hit_contract(self):
        class Engine:
            def preview(self,rgb,points,key):
                self.rgb=rgb
                return np.ones(rgb.shape[:2],dtype=np.uint8),{'seconds':.1,'cache_hit':True}
        eng=Engine()
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=eng):
            response=self.client.post('/api/sam/preview',json=self.request)
        self.assertEqual(response.status_code,200)
        data=response.json()
        png=cv2.imdecode(np.frombuffer(base64.b64decode(data['mask']),np.uint8),cv2.IMREAD_UNCHANGED)
        self.assertEqual(png.shape,(48,64,4))
        self.assertEqual(list(png[0,0]),[255,255,0,115])
        self.assertTrue(data['cache_hit'])
        self.assertFalse(data['empty'])

    def test_limits_device_and_local_frame(self):
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS):
            for update in ({'device':'cuda'},{'frame':3},{'end_frame':151}):
                self.assertEqual(self.client.post('/api/sam/preview',json={**self.request,**update}).status_code,422)
            server.MEDIA[self.media]['width']=1281
            self.assertEqual(self.client.post('/api/sam/preview',json=self.request).status_code,422)

    def test_long_segment_allows_single_frame_preview_but_blocks_propagation(self):
        server.MEDIA[self.media]['frames']=6454
        class Engine:
            def preview(self,rgb,points,key):
                return np.ones(rgb.shape[:2],dtype=np.uint8),{'seconds':.1,'cache_hit':False}
        request={**self.request,'end_frame':6454}
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=Engine()):
            response=self.client.post('/api/sam/preview',json=request)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['width'],64)
            analyze={k:v for k,v in request.items() if k!='frame'}
            analyze['prompts']={'0':request['prompts']}
            rejected=self.client.post('/api/sam/analyze',json=analyze)
            self.assertEqual(rejected.status_code,422)
            self.assertIn('传播最多 150 帧',rejected.json()['detail'])
            self.assertFalse(sam_service.SAM_LOCK.locked())

    def test_empty_preview_returns_transparent_png_and_releases_lock(self):
        class Engine:
            def preview(self,rgb,points,key):
                return np.zeros(rgb.shape[:2],dtype=np.uint8),{'seconds':.1,'cache_hit':False}
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=Engine()):
            response=self.client.post('/api/sam/preview',json=self.request)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertTrue(data['empty'])
        png=cv2.imdecode(np.frombuffer(base64.b64decode(data['mask']),np.uint8),cv2.IMREAD_UNCHANGED)
        self.assertEqual(png.shape,(48,64,4))
        self.assertFalse(np.any(png[:,:,3]))
        self.assertFalse(sam_service.SAM_LOCK.locked())

    def test_preview_missing_or_bad_shape_still_fails(self):
        for mask in (None,np.zeros((47,64),np.uint8)):
            with self.subTest(mask=None if mask is None else mask.shape):
                eng=Mock()
                eng.preview.return_value=(mask,{'seconds':.1,'cache_hit':False})
                with patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=eng),patch.dict(sam_service.ENGINES,{},clear=True):
                    response=self.client.post('/api/sam/preview',json=self.request)
                self.assertIn(response.status_code,(422,503))
                self.assertFalse(sam_service.SAM_LOCK.locked())

    def test_frozen_masks_and_playback_metadata(self):
        a=self.analysis()
        with self.assertRaises(ValueError):
            a.custom_masks[0].flags.writeable=True
        data=self.client.get('/api/playback/sam-test-analysis').json()
        self.assertEqual(data['shapes'],[[],[],[]])
        self.assertTrue(data['custom'])
        self.assertEqual(data['sam_device'],'cpu')
        png=self.client.get('/api/sam/mask/sam-test-analysis/0.png')
        self.assertEqual(png.status_code,200)
        alpha=cv2.imdecode(np.frombuffer(png.content,np.uint8),cv2.IMREAD_UNCHANGED)[:,:,3]
        self.assertEqual(set(np.unique(alpha)),{0,255})

    def test_custom_target_isolation_and_strict_export(self):
        self.analysis(False)
        self.assertEqual(self.client.post('/api/export/sam-test-analysis',data={'target':'custom'}).status_code,409)
        a=self.analysis()
        baseline=self.client.get('/api/preview/sam-test-analysis',params={'target':''}).content
        custom=self.client.get('/api/preview/sam-test-analysis',params={'target':'custom','style':'black'}).content
        self.assertNotEqual(baseline,custom)
        bad=server.Analysis(self.path,((),),64,48,25,face_ids=((),),custom_masks=(np.zeros((47,64),np.uint8),))
        with self.assertRaises(Exception):
            sam_service.require_custom(bad)
        self.assertEqual(server.select_regions((),(),('custom',)),())
        self.assertEqual(('face','plate'),server.parse_options('all',68,'black')[0])

    def test_empty_and_mixed_masks_preview_and_export_contract(self):
        base=self.analysis()
        empty=np.zeros((48,64),np.uint8)
        cap=cv2.VideoCapture(str(self.path))
        source=[]
        try:
            for _ in range(3):
                ok,frame=cap.read()
                self.assertTrue(ok)
                source.append(frame)
        finally:
            cap.release()
        real_capture=cv2.VideoCapture
        output=Path(self.tmp.name)/'output.mp4'
        for masks in ((empty,empty,empty),(base.custom_masks[0],empty,base.custom_masks[2])):
            with self.subTest(nonempty=[bool(np.any(m)) for m in masks]):
                analysis=replace(base,custom_masks=masks)
                server.ANALYSES['sam-test-analysis']=analysis
                sam_service.require_custom(analysis)
                for i,mask in enumerate(masks):
                    baseline=self.client.get('/api/preview/sam-test-analysis',params={'frame':i,'target':''})
                    custom=self.client.get('/api/preview/sam-test-analysis',params={'frame':i,'target':'custom','style':'black'})
                    self.assertEqual(custom.status_code,200)
                    self.assertEqual(custom.content==baseline.content,not bool(np.any(mask)))
                written=[]
                writer=Mock()
                writer.isOpened.return_value=True
                check=Mock()
                check.isOpened.return_value=True
                check.read.side_effect=lambda:(True,written.pop(0).copy()) if written else (False,None)
                captured=[]
                writer.write.side_effect=lambda frame:(written.append(frame.copy()),captured.append(frame.copy()))
                def capture(path):
                    return check if str(path)==str(output) else real_capture(path)
                with patch('inkshield.server.cv2.VideoCapture',side_effect=capture),patch('inkshield.server.cv2.VideoWriter',return_value=writer):
                    server.export_video('sam-test-analysis',analysis,output,('custom',),68,'black')
                self.assertEqual(server.JOBS['sam-test-analysis']['state'],'done')
                self.assertEqual(len(captured),3)
                writer.release.assert_called_once()
                check.release.assert_called_once()
                for original,rendered,mask in zip(source,captured,masks):
                    self.assertEqual(np.array_equal(original,rendered),not bool(np.any(mask)))

    def test_missing_and_badshape_masks_block_preview_and_export(self):
        base=self.analysis()
        for masks in ((),(base.custom_masks[0],),
                      (np.zeros((47,64),np.uint8),)*3,
                      (np.zeros((48,64),np.float32),)*3):
            with self.subTest(count=len(masks),dtype=masks[0].dtype if masks else None):
                server.ANALYSES['sam-test-analysis']=replace(base,custom_masks=masks)
                self.assertEqual(self.client.get('/api/preview/sam-test-analysis',params={'target':'custom'}).status_code,409)
                self.assertEqual(self.client.post('/api/export/sam-test-analysis',data={'target':'custom'}).status_code,409)

    def test_six_styles_preserve_outside_mask_and_dilate(self):
        rng=np.random.default_rng(4)
        frame=rng.integers(0,255,(48,64,3),dtype=np.uint8)
        mask=np.zeros((48,64),np.uint8);mask[18:24,25:31]=1
        for style in server.MASK_STYLES:
            changed=frame.copy()
            sam_service.apply_custom(changed,mask,68,style)
            np.testing.assert_array_equal(changed[:10],frame[:10])
            self.assertFalse(np.array_equal(changed[12:30,19:37],frame[12:30,19:37]))

    def test_analyze_prompt_keys_and_positive_each_frame(self):
        request={k:v for k,v in self.request.items() if k!='frame'}
        with patch('inkshield.sam_engine.capabilities',return_value=CAPS):
            for prompts in ({'01':self.request['prompts']},{'3':self.request['prompts']},{'0':[{'x':20,'y':20,'label':0}]}):
                self.assertEqual(self.client.post('/api/sam/analyze',json={**request,'prompts':prompts}).status_code,422)

    def test_analyze_missing_or_badshape_masks_never_publish_and_release_resources(self):
        class ImmediateThread:
            def __init__(self,target,args,**kwargs):
                self.target,self.args=target,args
            def start(self):
                self.target(*self.args)
        request={k:v for k,v in self.request.items() if k!='frame'}
        request['prompts']={'0':self.request['prompts']}
        runtime=Path(self.tmp.name)/'runtime';runtime.mkdir()
        valid=np.zeros((48,64),np.uint8)
        for masks in ({0:valid,2:valid},{0:valid,1:np.zeros((47,64),np.uint8),2:valid}):
            with self.subTest(keys=list(masks)):
                eng=Mock()
                eng.segment.return_value=(masks,{'total_seconds':.1})
                with patch.object(server,'RUNTIME',runtime),patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=eng),patch.dict(sam_service.ENGINES,{},clear=True),patch('inkshield.sam_service.threading',type('Threads',(),{'Thread':ImmediateThread})):
                    response=self.client.post('/api/sam/analyze',json=request)
                self.assertEqual(response.status_code,200)
                job_id=response.json()['job_id']
                try:
                    self.assertEqual(server.JOBS[job_id]['state'],'error')
                    self.assertNotIn(job_id,server.ANALYSES)
                    self.assertFalse((runtime/'sam'/job_id).exists())
                    self.assertFalse(sam_service.SAM_LOCK.locked())
                    permits=[]
                    try:
                        for _ in range(server.MAX_ACTIVE_JOBS):
                            acquired=server.ACTIVE_JOBS.acquire(blocking=False)
                            self.assertTrue(acquired)
                            if acquired:
                                permits.append(True)
                    finally:
                        for _ in permits:
                            server.ACTIVE_JOBS.release()
                finally:
                    server.JOBS.pop(job_id,None)
                    server.ANALYSES.pop(job_id,None)

    def test_analyze_publishes_ready_atomic_and_respects_persistent_quota(self):
        class ImmediateThread:
            def __init__(self,target,args,**kwargs):
                self.target,self.args=target,args
            def start(self):
                self.target(*self.args)
        class Engine:
            def segment(self,directory,prompts,count,progress):
                self.assert_frames=list(Path(directory).glob('*.jpg'))
                return {i:np.full((48,64),i != 1,np.uint8) for i in range(count)}, {'total_seconds':.1}
        request={k:v for k,v in self.request.items() if k!='frame'}
        request['prompts']={'1':self.request['prompts']}
        runtime=Path(self.tmp.name)/'runtime';runtime.mkdir()
        with patch.object(server,'RUNTIME',runtime),patch('inkshield.sam_engine.capabilities',return_value=CAPS),patch('inkshield.sam_service.engine',return_value=Engine()),patch('inkshield.sam_service.threading',type('Threads',(),{'Thread':ImmediateThread})):
            response=self.client.post('/api/sam/analyze',json=request)
            self.assertEqual(response.status_code,200)
            job_id=response.json()['job_id']
            try:
                status=self.client.get('/api/status/'+job_id).json()
                self.assertEqual(status['state'],'ready')
                self.assertEqual(status['frames'],3)
                self.assertTrue(status['custom'])
                self.assertEqual(status['sam_device'],'cpu')
                propagation={'anchor_frames':[1],'directions':['forward','backward'],
                             'covered_frames':3,'empty_frame_indices':[1]}
                self.assertEqual(status['sam_propagation'],propagation)
                payload=json.loads((runtime/'sam'/job_id/'sam.json').read_text(encoding='utf-8'))
                self.assertEqual(payload['sam_propagation'],propagation)
                analysis=server.ANALYSES[job_id]
                self.assertEqual(analysis.boxes,((),(),()))
                self.assertFalse(analysis.custom_masks[0].flags.writeable)
                self.assertTrue(np.any(analysis.custom_masks[0]))
                self.assertFalse(np.any(analysis.custom_masks[1]))
                self.assertTrue(np.any(analysis.custom_masks[2]))
                empty_png=self.client.get(f'/api/sam/mask/{job_id}/1.png')
                self.assertEqual(empty_png.status_code,200)
                decoded=cv2.imdecode(np.frombuffer(empty_png.content,np.uint8),cv2.IMREAD_UNCHANGED)
                self.assertFalse(np.any(decoded[:,:,3]))
                self.assertFalse((runtime/'sam'/job_id/'frames').exists())
                extra_ids = []
                for i in range(6):
                    created = self.client.post('/api/sam/analyze',json=request)
                    self.assertEqual(created.status_code,200,created.text)
                    extra_ids.append(created.json()['job_id'])
                for existing_id in [job_id] + extra_ids:
                    masks = server.ANALYSES[existing_id].custom_masks
                    self.assertIsInstance(masks, sam_service.DiskMasks)
                    self.assertFalse(masks[0].flags.writeable)
                    with self.assertRaises(ValueError):
                        masks[0].flags.writeable = True
                    self.assertEqual(self.client.get(f'/api/sam/mask/{existing_id}/0.png').status_code,200)
                for existing_id in extra_ids:
                    server.JOBS.pop(existing_id,None)
                    server.ANALYSES.pop(existing_id,None)
                self.assertFalse(sam_service.SAM_LOCK.locked())
            finally:
                server.JOBS.pop(job_id,None)
                server.ANALYSES.pop(job_id,None)


if __name__=='__main__':
    unittest.main()
