"""Cached workflow regression: geometry, API and one real video analysis."""
import time
import os
from pathlib import Path
import cv2
import numpy as np
from fastapi.testclient import TestClient
import masking
import server


def geometry():
    a=(30,35,42,43,.9,17)
    b=(63,48,75,56,.9,17)
    owner=(10,10,95,90,.9,7)
    shapes=masking.build_shapes([a,b],[owner,a,b])
    assert len(shapes)==1 and shapes[0][0]=='rectangle'
    assert abs(shapes[0][-1]-np.arctan2(13,33))<1e-8
    image=np.full((100,110,3),255,np.uint8)
    masking.apply_masks(image,[a,b],68,'black',[owner,a,b])
    assert np.all(image[45,52]==0), 'inter-eye bridge missing'
    assert np.all(image[0,0]==255)
    assert masking.build_shapes([a],[owner,a])[0][0]=='ellipse'
    other=(58,42,100,95,.9,7)
    small_owner=(10,10,55,90,.9,7)
    assert len(masking.build_shapes([a,b],[small_owner,other,a,b]))==2
    # Overlapping ambiguous heads do not merge two unowned eyes.
    assert len(masking.build_shapes([a,b],[owner,owner,a,b]))==2
    assert len(masking.build_shapes([a,b]))==2
    for style in ('black','blur','mosaic'):
        sample=np.random.default_rng(1).integers(0,256,(100,110,3),dtype=np.uint8)
        before=sample.copy()
        masking.apply_masks(sample,[a,b],68,style,[owner,a,b])
        assert np.array_equal(sample[:20],before[:20])
    for style in ('black','blur','mosaic'):
        tiny=np.full((10,10,3),255,np.uint8)
        masking.apply_masks(tiny,[(.5,.5,1.5,1.5,.9,17)],68,style)
        assert np.any(tiny<255),style
    assert len(masking.build_shapes([(10,20,20,26,.9,17),(70,20,80,26,.9,17)],[(0,0,100,100,.9,7)]))==2
    assert masking.build_shapes([a],[(0,0,100,100,.9,float('nan'))])[0][0]=='ellipse'
    print('geometry PASS',flush=True)


def wait(client,job,terminal):
    start=time.monotonic()
    while time.monotonic()-start<180:
        status=client.get('/api/status/'+job).json()
        if status['state']=='error':
            raise AssertionError(status)
        if status['state'] in terminal:
            return status
        time.sleep(.1)
    raise AssertionError('job timeout')


def run():
    geometry()
    source=Path(os.environ.get('INKSHIELD_TEST_VIDEO',str(server.RUNTIME/'mask-test-input.mp4')))
    assert source.is_file(), source
    detector=server.get_detector()
    plate_detector=server.get_plate_detector()
    original_plate=plate_detector.detect
    plate_calls=[]
    def counted_plate(frame,threshold=server.HEAD_THRESHOLD):
        plate_calls.append(threshold)
        return original_plate(frame,threshold=threshold)
    plate_detector.detect=counted_plate
    original=detector.detect
    calls=[]
    def counted(frame,targets=('head',),threshold=server.HEAD_THRESHOLD):
        calls.append(tuple(targets))
        return original(frame,targets,threshold=threshold)
    detector.detect=counted
    with TestClient(server.app) as client:
        with source.open('rb') as stream:
            response=client.post('/api/analyze',files={'video':('sample.mp4',stream,'video/mp4')})
        assert response.status_code==200,response.text
        job=response.json()['job_id']
        status=wait(client,job,{'ready'})
        count=len(calls)
        assert count==status['frames'] and count>0,(count,status)
        assert all(set(t)==set(server.HUMAN_TARGETS) for t in calls)
        print('analysis PASS',status,flush=True)
        def forbidden(*args,**kwargs):
            raise AssertionError('Preview/export must NEVER invoke detection')
        assert len(plate_calls)==count
        detector.detect=forbidden
        plate_detector.detect=forbidden
        playback=client.get('/api/playback/'+job)
        assert playback.status_code==200,playback.text
        geometry_data=playback.json()
        assert geometry_data['frames']==count and len(geometry_data['shapes'])==count
        for rows in geometry_data['shapes']:
            for row in rows:
                assert len(row)==7 and row[0] in ('ellipse','rectangle') and row[6] in server.PART_CLASSES.values()
        print('playback geometry PASS (ZERO inference)',flush=True)
        for frame,target,style in [(0,'eyes','black'),(status['frames']-1,'eyes,mouth','blur'),(0,'head,face,eyes,nose,mouth,ears,plate','mosaic')]:
            r=client.get('/api/preview/'+job,params={'frame':frame,'target':target,'style':style,'strength':90})
            assert r.status_code==200,r.text
            decoded=cv2.imdecode(np.frombuffer(r.content,np.uint8),cv2.IMREAD_COLOR)
            assert decoded is not None and decoded.shape[:2]==(status['height'],status['width'])
        for params in ({'frame':status['frames']},{'target':'bad'},{'style':'bad'}):
            r=client.get('/api/preview/'+job,params=params)
            assert r.status_code in (400,422),r.text
        for target,style in [('plate','black'),('eyes,mouth,plate','mosaic')]:
            r=client.post('/api/export/'+job,data={'target':target,'style':style,'strength':68})
            assert r.status_code==200,r.text
            exported=wait(client,r.json()['job_id'],{'done'})
            download=client.get(exported['download'])
            assert download.status_code==200 and len(download.content)>100
            print('export PASS',exported,flush=True)
        print('CACHE/API PASS: analysis detection calls',count,'preview and exports ZERO',flush=True)
    detector.detect=original
    plate_detector.detect=original_plate

if __name__=='__main__':
    run()
