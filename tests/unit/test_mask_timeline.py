"""Timeline contract, JPEG/MP4 pixels and protected-video cache regression."""
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
import cv2
import numpy as np
from fastapi import HTTPException
from inkshield import server
from inkshield.mask_timeline import normalize_regions, regions_json
from tests.unit import test_preview_video as preview_tests


def region(start=2, end=4, **changes):
    item = dict(id='effect-1', start=start, end=end, style='black', strength=68,
                targets=['custom'], faceMode='all', faceShape='circumscribed',
                personIds=[], maskPending=True)
    item.update(changes)
    return item


class TimelineTests(unittest.TestCase):
    setUp = preview_tests.PreviewVideoTests.setUp
    restore = preview_tests.PreviewVideoTests.restore
    fixture = preview_tests.PreviewVideoTests.fixture
    wait = preview_tests.PreviewVideoTests.wait

    def timeline_post(self, value):
        return self.client.post('/api/custom-playback/custom', data={'style':'black', 'mask_regions':json.dumps(value)})

    def decode(self, path):
        cap = cv2.VideoCapture(str(path))
        frames = []
        try:
            while True:
                ok, image = cap.read()
                if not ok: break
                frames.append(image)
        finally:
            cap.release()
        return frames

    def assert_interval_pixels(self, frames, empty=False):
        self.assertEqual(len(frames), 6)
        for index, image in enumerate(frames):
            mean = image[25:35, 30:50].mean()
            if not empty and 2 <= index < 4:
                self.assertLess(mean, 8, (index, mean))
            else:
                self.assertGreater(mean, 230, (index, mean))

    def test_custom_real_codec_jpeg_export_cache_and_empty(self):
        self.fixture(audio=True, odd=False)
        value = [region()]
        for index in range(6):
            response = self.client.get('/api/preview/custom', params={'frame': index,'target':'custom','mask_regions':json.dumps(value)})
            self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else '')
            decoded = cv2.imdecode(np.frombuffer(response.content,np.uint8),cv2.IMREAD_COLOR)
            mean = decoded[25:35,30:50].mean()
            self.assertTrue(mean < 8 if 2 <= index < 4 else mean > 230, (index,mean))
        first = self.timeline_post(value).json()
        job = self.wait(first['job_id'])
        self.assertEqual(job['state'], 'done', job)
        self.assertTrue(job['audio_present'])
        self.assert_interval_pixels(self.decode(self.root / first['job_id'] / 'playback.mp4'))
        self.assertEqual(self.timeline_post(value).json()['job_id'],first['job_id'])
        for changed in ([region(1,4)], [region(style='mosaic')], []):
            response = self.timeline_post(changed)
            self.assertEqual(response.status_code,200,response.text)
            new = response.json()
            self.assertNotEqual(new['job_id'], first['job_id'])
            result = self.wait(new['job_id'])
            self.assertEqual(result['state'],'done',result)
            if not changed:
                self.assert_interval_pixels(self.decode(self.root / new['job_id'] / 'playback.mp4'),empty=True)
        for config in (value, []):
            response = self.client.post('/api/export/custom',data={'target':'custom','muted':'false','mask_regions':json.dumps(config)})
            self.assertEqual(response.status_code,200,response.text)
            result = self.wait(response.json()['job_id'])
            self.assertEqual(result['state'],'done',result)
            self.assertTrue(result['audio_present'])
            self.assert_interval_pixels(self.decode(self.root / result['job_id'] / 'output.mp4'), empty=not config)

    def test_malformed_all_routes_and_snapshot(self):
        analysis = self.fixture(audio=False, odd=False)
        valid = [region()]
        normalized = normalize_regions(valid, analysis)
        valid[0]['targets'].clear()
        valid[0]['start'] = 0
        self.assertEqual(normalized[0].targets,('custom',))
        self.assertEqual(normalized[0].start,2)
        self.assertEqual(json.loads(regions_json(normalized))[0]['targets'],['custom'])
        invalid = [None, {}, [dict(id='x')], [region(start=True)], [region(start=-1)],
                   [region(end=7)], [region(start=4,end=4)], [region(strength=True)],
                   [region(strength=101)], [region(style='bad')], [region(targets=['face'])],
                   [region(personIds=[1])], [region(maskPending=1)], [region(faceMode='bad')],
                   [region(),region(4,5)], [region(),region(3,5,id='other')]]
        for value in invalid:
            encoded = json.dumps(value)
            for route in ('preview','export','custom-playback'):
                with self.subTest(value=value,route=route):
                    response = (self.client.get('/api/preview/custom',params={'mask_regions':encoded}) if route=='preview'
                                else self.client.post('/api/'+route+'/custom',data={'mask_regions':encoded}))
                    self.assertEqual(response.status_code,422,response.text)
        for encoded in ('', '{', 'true'):
            self.assertEqual(self.client.get('/api/preview/custom',params={'mask_regions':encoded}).status_code,422)
            self.assertEqual(self.client.post('/api/export/custom',data={'mask_regions':encoded}).status_code,422)
            self.assertEqual(self.client.post('/api/custom-playback/custom',data={'mask_regions':encoded}).status_code,422)
        self.assertEqual(len(server.CUSTOM_PLAYBACK_CACHE),0)

    def test_automatic_local_boundaries_gaps_and_empty(self):
        analysis = self.fixture(audio=False, odd=False)
        boxes = ((20,15,60,45,.95,16),)
        auto = replace(analysis, custom_masks=(), boxes=(boxes,)*6, face_ids=((None,),)*6)
        server.ANALYSES['custom'] = auto
        configs = [region(0,1,targets=['face']),region(5,6,id='last',targets=['face'])]
        for index in range(6):
            response = self.client.get('/api/preview/custom',params={'frame':index,'mask_regions':json.dumps(configs)})
            self.assertEqual(response.status_code,200)
            image=cv2.imdecode(np.frombuffer(response.content,np.uint8),cv2.IMREAD_COLOR)
            mean=image[25:35,30:50].mean()
            self.assertTrue(mean<8 if index in (0,5) else mean>230,(index,mean))
        self.assertEqual(normalize_regions([],auto),())
        with self.assertRaises(HTTPException): normalize_regions([region()],auto)
        adjacent=[region(0,3,targets=['face']),region(3,6,id='adjacent',targets=['plate'])]
        self.assertEqual(len(normalize_regions(adjacent,auto)),2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
