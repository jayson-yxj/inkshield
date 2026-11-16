"""Integration contract: plate cache drives all render paths with no inference."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

from types import SimpleNamespace
import cv2
import numpy as np
from fastapi.testclient import TestClient
from inkshield import server
from inkshield.masking import build_shapes, apply_masks
from verify_cached import wait

box=(20.,20.,80.,40.,.9,21)
assert build_shapes([box])==[('rectangle',50.,30.,37.5,12.5,0.)]
image=np.full((80,100,3),255,np.uint8)
apply_masks(image,[box],68,'black')
assert np.all(image[20:40,20:80]==0), 'detected rectangle must be fully opaque'
assert np.all(image[:10]==255)
source=server.RUNTIME/'mask-test-input.mp4'
calls=[]
# Synthetic contract test does not require plate weights on disk.
server.PLATE_MODEL_PATH=server.MODEL_PATH
server.get_detector=lambda:SimpleNamespace(detect=lambda frame,targets,threshold: [])
def plate(frame,threshold):
    calls.append(threshold)
    return [box]
server.get_plate_detector=lambda:SimpleNamespace(detect=plate)
with TestClient(server.app) as client:
    with source.open('rb') as stream:
        r=client.post('/api/analyze',data={'threshold':'.45'},files={'video':('test.mp4',stream,'video/mp4')})
    assert r.status_code==200,r.text
    job=r.json()['job_id']; status=wait(client,job,{'ready'})
    assert len(calls)==status['frames'] and set(calls)=={.45}
    assert server.ANALYSES[job].boxes[0]==(box,)
    def forbidden(*args,**kwargs): raise AssertionError('cached operation called model')
    server.get_detector=server.get_plate_detector=forbidden
    data=client.get('/api/playback/'+job).json()
    assert data['shapes'][0]==[['rectangle',50.,30.,37.5,12.5,0.,21]]
    for style in server.MASK_STYLES:
        r=client.get('/api/preview/'+job,params={'target':'plate','style':style})
        assert r.status_code==200,r.text
        assert cv2.imdecode(np.frombuffer(r.content,np.uint8),1) is not None
    r=client.post('/api/export/'+job,data={'target':'plate','style':'black'})
    assert r.status_code==200,r.text
    result=wait(client,r.json()['job_id'],{'done'})
    cap=cv2.VideoCapture(str(server.RUNTIME/r.json()['job_id']/'output.mp4'))
    count=0
    while True:
        ok,frame=cap.read()
        if not ok:break
        assert np.max(frame[24:36,24:76])<20
        count+=1
    cap.release()
    assert count==status['frames'],(count,status)
print('PLATE CACHE PASS: threshold, geometry, opaque bbox, JPEG all styles, playback, full export redecode; ZERO cached inference')
