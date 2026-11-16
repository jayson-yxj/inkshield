"""Ordered multi-analysis HTTP composition with actual H264 and export decoding."""
import json
from dataclasses import replace
from unittest.mock import patch
import numpy as np
import cv2
from tests.unit.test_preview_video import PreviewVideoTests
from inkshield import server
from inkshield import sam_service


class LayerTests(PreviewVideoTests):
    def layers_fixture(self):
        custom = self.fixture(audio=False, odd=False)
        auto = replace(custom, custom_masks=(), boxes=(((3,3,18,18,1.,21),),)*6, face_ids=((None,),)*6)
        mask=np.zeros((64,80),np.uint8); mask[42:55,60:74]=1; mask.flags.writeable=False
        second=replace(custom,custom_masks=(mask,)*6)
        for key,analysis in [('auto',auto),('second',second)]:
            server.new_job(key,'analysis',state='ready');server.ANALYSES[key]=analysis
        def region(target):
            return dict(id='r',start=0,end=6,style='black',strength=68,targets=[target],faceMode='all',faceShape='circumscribed',personIds=[],maskPending=True)
        return [dict(analysis_id=key,mask_regions=[region(target)]) for key,target in [('auto','plate'),('custom','custom'),('second','custom')]]

    def test_layers_preview_play_export(self):
        layers=self.layers_fixture();raw=json.dumps(layers)
        response=self.client.get('/api/preview/auto',params={'frame':1,'layers':raw})
        self.assertEqual(response.status_code,200,response.text)
        image=cv2.imdecode(np.frombuffer(response.content,np.uint8),1)
        for y,x in [(10,10),(30,40),(48,65)]: self.assertLess(image[y,x].mean(),10)
        zero=self.client.get('/api/preview/auto',params={'frame':1,'layers':'[]'})
        self.assertGreater(cv2.imdecode(np.frombuffer(zero.content,np.uint8),1).mean(),230)
        playback=self.client.post('/api/custom-playback/auto',data={'layers':raw}).json()
        self.assertEqual(self.wait(playback['job_id'])['state'],'done')
        reordered_json=json.dumps(layers,sort_keys=True,indent=2)
        self.assertEqual(self.client.post('/api/custom-playback/auto',data={'layers':reordered_json}).json()['job_id'],playback['job_id'])
        export=self.client.post('/api/export/auto',data={'layers':raw}).json()
        self.assertEqual(self.wait(export['job_id'])['state'],'done')
        for job,name in [(playback,'playback.mp4'),(export,'output.mp4')]:
            cap=cv2.VideoCapture(str(self.root/job['job_id']/name));cap.read();ok,image=cap.read();cap.release()
            self.assertTrue(ok)
            for y,x in [(10,10),(30,40),(48,65)]: self.assertLess(image[y,x].mean(),15)
        changed=list(reversed(layers))
        other=self.client.post('/api/custom-playback/auto',data={'layers':json.dumps(changed)}).json()
        self.assertNotEqual(other['job_id'],playback['job_id']);self.assertEqual(self.wait(other['job_id'])['state'],'done')

    def test_layer_order_and_intralayer_overlap(self):
        from inkshield.mask_layers import normalize_layers, apply_layers
        layers=self.layers_fixture()
        snapshot=normalize_layers(server,server.ANALYSES['auto'],layers)
        calls=[]
        with patch('inkshield.mask_layers.apply_frame_config',side_effect=lambda api,frame,analysis,index,regions: calls.append(analysis) or 1):
            self.assertEqual(apply_layers(server,np.zeros((64,80,3),np.uint8),1,snapshot),3)
        self.assertEqual([id(a) for a in calls],[id(server.ANALYSES[key]) for key in ['auto','custom','second']])
        layers[1]['mask_regions'].append(dict(layers[1]['mask_regions'][0],id='overlap'))
        self.assertEqual(self.client.post('/api/export/auto',data={'layers':json.dumps(layers)}).status_code,422)

    def test_bad_layers_all_endpoints(self):
        layers=self.layers_fixture()
        for field,value in [('start_frame',4),('fps',24),('width',81),('input_path',self.root/'other.mp4'),('boxes',((),))]:
            original=server.ANALYSES['second'];server.ANALYSES['second']=replace(original,**{field:value})
            try:
                raw=json.dumps(layers)
                self.assertEqual(self.client.get('/api/preview/auto',params={'layers':raw}).status_code,422)
                for path in ['export','custom-playback']:
                    self.assertEqual(self.client.post(f'/api/{path}/auto',data={'layers':raw}).status_code,422)
            finally: server.ANALYSES['second']=original
        for raw in ['null','{}','bad',json.dumps([{'analysis_id':'auto'}])]:
            self.assertEqual(self.client.get('/api/preview/auto',params={'layers':raw}).status_code,422)
        self.assertEqual(self.client.post('/api/export/auto',data={'layers':'[]','mask_regions':'[]'}).status_code,422)

    def test_disk_manifest_and_low_space(self):
        self.fixture(audio=False,odd=False)
        directory=self.root/'masks';directory.mkdir()
        for i in range(6): np.save(directory/f'{i}.npy',np.zeros((64,80),np.uint8))
        masks=sam_service.DiskMasks(directory,6,(64,80))
        analysis=replace(server.ANALYSES['custom'],custom_masks=masks)
        server.ANALYSES['custom']=analysis
        with patch('numpy.load',side_effect=AssertionError('validation must not load pixels')):
            sam_service.require_custom(analysis)
        np.save(directory/'2.npy',np.zeros((1,1),np.uint8))
        self.assertEqual(self.client.get('/api/preview/custom',params={'target':'custom'}).status_code,409)
        with patch('inkshield.sam_service.shutil.disk_usage',return_value=type('Usage',(),{'free':1})()):
            with self.assertRaises(Exception) as caught: sam_service.require_disk_space(self.root,100)
            self.assertEqual(caught.exception.status_code,507)

    def test_preview_index_eviction_keeps_url(self):
        self.fixture(audio=False,odd=False)
        with patch('inkshield.preview_video.MAX_CACHED_PREVIEWS',1):
            first=self.post('black').json();self.assertEqual(self.wait(first['job_id'])['state'],'done')
            second=self.post('blur').json();self.assertEqual(self.wait(second['job_id'])['state'],'done')
            self.assertEqual(len(server.CUSTOM_PLAYBACK_CACHE),1)
            self.assertEqual(self.client.get('/api/custom-playback-video/'+first['job_id']).status_code,200)
