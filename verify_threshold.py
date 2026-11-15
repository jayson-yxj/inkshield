"""Per-analysis confidence threshold validation and immutable cache metadata."""
import json
import time
from types import SimpleNamespace
import numpy as np
from fastapi.testclient import TestClient
import server

# Exercise production score filtering without loading a neural network.
detector=object.__new__(server.HeadDetector)
detector.input=SimpleNamespace(shape=[1,3,'H','W'],name='input')
detector.output_name='output'
rows=np.array([[[17,.1,.1,.3,.3,.2],[19,.4,.4,.6,.6,.6],[16,.1,.1,.9,.9,.9]]],dtype=np.float32)
detector.session=SimpleNamespace(run=lambda *args:[rows])
frame=np.zeros((16,16,3),np.uint8)
assert len(detector.detect(frame,tuple(server.PART_CLASSES)))==2
assert len(detector.detect(frame,tuple(server.PART_CLASSES),threshold=.1))==3
assert len(detector.detect(frame,tuple(server.PART_CLASSES),threshold=.8))==1

# Actual upload/worker/cache flow; fake inference only, real short video decode.
source=server.RUNTIME/'mask-test-input.mp4'
assert source.is_file()
calls=[]
def detect(frame, targets, threshold):
    calls.append(threshold)
    return detector.detect(frame,targets,threshold)
server.get_detector=lambda:SimpleNamespace(detect=detect)
server.get_plate_detector=lambda:SimpleNamespace(detect=lambda frame,threshold: [])
server.PLATE_MODEL_PATH=server.MODEL_PATH  # synthetic detector; no plate weights needed
with TestClient(server.app) as client:
    for value in ('0.01','0.99','nan','inf','bad'):
        response=client.post('/api/analyze',data={'threshold':value},files={'video':('x.mp4',b'x','video/mp4')})
        assert response.status_code==422,(value,response.text)
    for value in (None,'0.15','0.85'):
        start=len(calls)
        data={} if value is None else {'threshold':value}
        with source.open('rb') as stream:
            response=client.post('/api/analyze',data=data,files={'video':('x.mp4',stream,'video/mp4')})
        assert response.status_code==200,response.text
        job=response.json()['job_id']
        deadline=time.monotonic()+30
        while True:
            status=client.get('/api/status/'+job).json()
            if status['state'] in ('ready','error'):break
            assert time.monotonic()<deadline
            time.sleep(.02)
        assert status['state']=='ready',status
        expected=.5 if value is None else float(value)
        assert status['threshold']==expected and set(calls[start:])=={expected}
        analysis=server.ANALYSES[job]
        payload=json.loads((server.RUNTIME/job/'detections.json').read_text(encoding='utf-8'))
        assert payload['threshold']==expected
        assert len(analysis.boxes[0])==({.5:2,.15:3,.85:1}[expected])
print('THRESHOLD PASS: default/custom filtering, form range/NaN rejection, frozen per-job inference, persisted cache threshold')
