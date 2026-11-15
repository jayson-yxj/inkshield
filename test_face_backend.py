"""Small inference-independent regression suite for cached identity selection."""
import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cv2
import numpy as np
from fastapi import HTTPException
from fastapi.testclient import TestClient
import server
from face_detector import align_face, FaceDetector
from identity_gallery import IdentityGallery


class FaceBackendTests(unittest.TestCase):
    def test_selection_and_validation(self):
        boxes = ((0,0,10,10,.9,16),(10,0,20,10,.9,16),(0,20,20,30,.9,21))
        analysis = server.Analysis(Path('unused'), (boxes,), 32,32,25, face_ids=((1,None,None),), people=({'id':1,'count':1,'thumbnail':''},))
        self.assertEqual(server.select_regions(boxes, analysis.face_ids[0], ('face','plate'), 'selected'), boxes[1:])
        self.assertEqual(server.select_regions(boxes, analysis.face_ids[0], ('face','plate'), 'selected', frozenset({1}), False), (boxes[0],boxes[2]))
        self.assertEqual(server.select_regions(boxes, analysis.face_ids[0], ('face',), 'all', frozenset(), False), boxes[:2])
        self.assertEqual(server.select_regions(boxes, analysis.face_ids[0], ('plate',), 'selected', frozenset(), False), boxes[2:])
        for ids in ('0','-1','1,','2','1.0'):
            with self.assertRaises(HTTPException): server.parse_face_selection(analysis, 'selected', ids)
        self.assertEqual(server.parse_face_selection(analysis, 'selected', '')[1], frozenset())
        with self.assertRaises(HTTPException): server.parse_options('head',68,'mosaic')
        with self.assertRaises(RuntimeError): server.select_regions(boxes, (), ('face',))

    def test_http_empty_targets_styles_and_cache_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'source.mp4'
            writer = cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),25,(80,80))
            self.assertTrue(writer.isOpened())
            rng = np.random.default_rng(44)
            for _ in range(2):
                writer.write(rng.integers(40,220,(80,80,3),dtype=np.uint8))
            writer.release()
            boxes = ((20,20,60,60,.95,16),(5,65,35,75,.9,21))
            analysis = server.Analysis(source,(boxes,boxes),80,80,25,face_ids=((None,None),)*2)
            server.new_job('http-cache','analysis',state='ready')
            server.ANALYSES['http-cache'] = analysis
            self.addCleanup(server.ANALYSES.pop,'http-cache',None)
            self.addCleanup(server.JOBS.pop,'http-cache',None)
            original_cache = analysis.boxes
            cap = cv2.VideoCapture(str(source))
            ok, decoded = cap.read(); cap.release()
            self.assertTrue(ok)
            ok, expected_jpeg = cv2.imencode('.jpg',decoded,[cv2.IMWRITE_JPEG_QUALITY,88])
            self.assertTrue(ok)
            workers = []
            def run_now(operation,*args):
                workers.append(args)
                self.addCleanup(server.JOBS.pop,args[0],None)
                server.run_worker(operation,*args)
            with patch.object(server,'RUNTIME',root), \
                 patch.object(server,'start_worker',side_effect=run_now), \
                 patch.object(server,'get_detector',side_effect=AssertionError('must not infer face')), \
                 patch.object(server,'get_plate_detector',side_effect=AssertionError('must not infer plate')), \
                 TestClient(server.app) as client:
                for style in server.MASK_STYLES:
                    with self.subTest(style=style):
                        raw = client.get('/api/preview/http-cache',params={'target':'','style':style})
                        self.assertEqual(raw.status_code,200)
                        self.assertEqual(raw.content,expected_jpeg.tobytes())
                        masked = client.get('/api/preview/http-cache',params={'style':style})
                        self.assertEqual(masked.status_code,200)
                        self.assertNotEqual(masked.content,raw.content)
                        result = client.post('/api/export/http-cache',data={'target':'','style':style})
                        self.assertEqual(result.status_code,200,result.text)
                        job = server.require_job(result.json()['job_id'])
                        self.assertEqual(job['targets'],[])
                        self.assertEqual(job['state'],'done',job)
                        self.assertEqual(job['regions'],0)
                        self.assertEqual(workers[-1][3],())
                        # Compare against the same codec without masks, avoiding a
                        # false requirement for lossless MP4 round trips.
                        baseline = root/f'baseline-{style}.mp4'
                        server.new_job('http-baseline','export')
                        self.addCleanup(server.JOBS.pop,'http-baseline',None)
                        server.export_video('http-baseline',analysis,baseline,(),68,style)
                        output = root/job['job_id']/'output.mp4'
                        self.assertEqual(output.read_bytes(),baseline.read_bytes())
                shape_images = {}
                for mode in ('inscribed','circumscribed'):
                    preview = client.get('/api/preview/http-cache',params={'target':'face','style':'black','face_shape':mode})
                    self.assertEqual(preview.status_code,200)
                    result = client.post('/api/export/http-cache',data={'target':'face','style':'black','face_shape':mode})
                    self.assertEqual(result.status_code,200,result.text)
                    job = server.require_job(result.json()['job_id'])
                    self.assertEqual(job['face_shape'],mode)
                    self.assertEqual(workers[-1][-1],mode)
                    cap = cv2.VideoCapture(str(root/job['job_id']/'output.mp4'))
                    ok, image = cap.read(); cap.release()
                    self.assertTrue(ok)
                    shape_images[mode] = image
                    expected = decoded.copy()
                    server.apply_masks(expected,boxes[:1],68,'black',face_shape=mode)
                    ok,jpeg = cv2.imencode('.jpg',expected,[cv2.IMWRITE_JPEG_QUALITY,88])
                    self.assertEqual(preview.content,jpeg.tobytes())
                # Ring pixel is beyond inscribed x radius but inside the
                # circumscribed opaque core; verify actual encoded export.
                self.assertGreater(shape_images['inscribed'][40,61].mean(),30)
                self.assertLess(shape_images['circumscribed'][40,61].mean(),10)
                self.assertEqual(client.get('/api/preview/http-cache',params={'face_shape':'invalid'}).status_code,422)
                self.assertEqual(client.post('/api/export/http-cache',data={'face_shape':'invalid'}).status_code,422)
                # Multipart emptiness must survive Form('face'), too.
                result = client.post('/api/export/http-cache',files={'target':(None,'')})
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(server.require_job(result.json()['job_id'])['targets'],[])
                result = client.post('/api/export/http-cache',data={'style':'black'})
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(server.require_job(result.json()['job_id'])['targets'],['face'])
                self.assertEqual(workers[-1][3],('face',))
                for target in ('head','face,',' ','unknown',','):
                    self.assertEqual(client.get('/api/preview/http-cache',params={'target':target}).status_code,422)
                    self.assertEqual(client.post('/api/export/http-cache',data={'target':target}).status_code,422)
                self.assertEqual(client.get('/api/preview/http-cache',params={'style':'invalid'}).status_code,422)
                self.assertEqual(client.post('/api/export/http-cache',data={'style':'invalid'}).status_code,422)
                shapes = client.get('/api/playback/http-cache').json()['shapes'][0]
                self.assertEqual([shape[0] for shape in shapes],['ellipse','rectangle'])
                self.assertIs(server.ANALYSES['http-cache'],analysis)
                self.assertIs(analysis.boxes,original_cache)

    def test_gallery_confirmation_and_conflict(self):
        gallery = IdentityGallery()
        v = np.array([1.,0.],dtype=np.float32)
        for _ in range(4): self.assertIsNone(gallery.update([v],[True])[0]['person'])
        self.assertEqual(gallery.update([v],[True])[0]['person'],1)
        result = gallery.update([v,v],[True,True])
        self.assertEqual(sum(r['person'] == 1 for r in result),1)
        self.assertEqual(len(gallery.people),1)
        with self.assertRaises(ValueError): gallery.update([np.zeros(2)],[True])
        with self.assertRaises(ValueError): align_face(np.zeros((32,32,3),np.uint8), np.ones((5,2)))
        with self.assertRaises(ValueError): align_face(np.zeros((32,32,3),np.uint8), np.full((5,2),np.nan))

    def test_analysis_enrollment_playback_and_export_no_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'input.mp4'
            writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'mp4v'),25,(80,80))
            self.assertTrue(writer.isOpened())
            for _ in range(6): writer.write(np.full((80,80,3),100,np.uint8))
            writer.release()
            face=SimpleNamespace(bbox=np.array([10,10,60,60]),det_score=.95,normed_embedding=np.array([1.,0.]),thumbnail_crop=np.zeros((112,112,3),np.uint8))
            detector=SimpleNamespace(detect=lambda *a,**kw:[face])
            plates=SimpleNamespace(detect=lambda *a,**kw:[(0.,65.,40.,75.,.9,21)])
            server.new_job('face-contract','analysis')
            with patch.object(server,'RUNTIME',root), patch.object(server,'get_detector',return_value=detector), patch.object(server,'get_plate_detector',return_value=plates):
                analysis=server.analyze_video('face-contract',source)
            self.assertEqual(analysis.face_ids,((None,None),)*4+((1,None),)*2)
            self.assertEqual(analysis.pending_count,4)
            self.assertEqual(analysis.people[0]['count'],2)
            thumb=cv2.imdecode(np.frombuffer(base64.b64decode(analysis.people[0]['thumbnail']),np.uint8),cv2.IMREAD_COLOR)
            self.assertEqual(thumb.shape,(112,112,3))
            with patch.object(server,'get_detector',side_effect=AssertionError('must not infer')):
                geometry=json.loads(server.playback('face-contract').body)
                self.assertTrue(all(len(shape)==8 for frame in geometry['shapes'] for shape in frame))
                self.assertEqual(geometry['shapes'][4][0][-1],1)
                self.assertIsNone(geometry['shapes'][4][1][-1])
                preview=server.preview('face-contract',4,'face',68,'black','selected','',True)
                self.assertEqual(preview.media_type,'image/jpeg')
                server.new_job('face-export','export')
                server.export_video('face-export',analysis,root/'output.mp4',('face','plate'),68,'black',True,'selected',frozenset(),True)
                self.assertEqual(server.require_job('face-export')['state'],'done')
            server.ANALYSES.pop('face-contract',None)
            server.JOBS.pop('face-contract',None);server.JOBS.pop('face-export',None)

if __name__=='__main__': unittest.main()
