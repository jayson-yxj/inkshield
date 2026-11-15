"""Geometry scaling regression; no model required."""
import math
import numpy as np
from masking import build_shapes, apply_masks
from fastapi.testclient import TestClient
from pathlib import Path
import server


def check(box, radii):
    shape, = build_shapes([box])
    assert np.allclose(shape[1:5], [50, 50, *radii]), shape
    return shape

check((40,45,60,55,.9,17), (12,6))
check((40,45,60,55,.9,19), (12,6))
check((40,30,60,70,.9,16), (11.5,20))
check((30,40,70,60,.9,16), (20,11.5))
check((40,40,60,60,.9,16), (11.5,10))
for cls in (7,18,20):
    check((40,45,60,55,.9,cls), (10,5))
head=(0,0,100,100,.9,7)
eyes=[(20,30,32,38,.9,17),(56,40,68,48,.9,17)]
shape,=build_shapes(eyes, context=[head,*eyes])
assert shape[0]=='rectangle'
c,s=math.cos(shape[-1]),math.sin(shape[-1])
corners=np.array([(b[x],b[y]) for b in eyes for x,y in ((0,1),(2,1),(2,3),(0,3))])
u=corners[:,0]*c+corners[:,1]*s
v=-corners[:,0]*s+corners[:,1]*c
assert np.allclose(shape[3:5], [(u.max()-u.min())*.6,(v.max()-v.min())*.6])
# Out-of-frame enlargement remains clipped safely for all styles.
for style in ('black','blur','mosaic'):
    image=np.random.default_rng(42).integers(0,256,(20,20,3),dtype=np.uint8)
    original=image.copy()
    apply_masks(image,[(0,0,8,8,.9,19)],68,style)
    assert np.any(image!=original) and np.array_equal(image[12:,12:],original[12:,12:])
with TestClient(server.app) as client:
    server.new_job('size-test','analysis',state='ready')
    server.ANALYSES['size-test']=server.Analysis(Path('unused.mp4'),(tuple([head,*eyes]),),100,100,30.)
    response=client.get('/api/playback/size-test')
    assert response.status_code==200,response.text
    eye_shapes=[q[:-1] for q in response.json()['shapes'][0] if q[-1]==17]
    assert np.allclose(eye_shapes[0][1:],shape[1:])
print('MASK SIZE PASS: single/paired eyes x1.2, mouth x1.2, face short axis x1.15, other parts unchanged, clipping and playback geometry')
