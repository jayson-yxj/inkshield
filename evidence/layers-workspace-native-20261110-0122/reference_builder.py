"""Independent layer/interval compositor; reuses established single-mask primitives.
Does not call normalize_layers, apply_layers, apply_frame_config or output routes.
This tests composition/transport/order, not correctness of the shared mask primitive.
"""
from pathlib import Path
import sys, json
import av, numpy as np
from PIL import Image
from controlled_fixtures import RECTS, ROIS
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

def build(out,payload,frames):
    from masking import apply_masks
    from sam_service import apply_custom
    selected=set(frames);rules=[];order=[]
    for frame_index,frame in enumerate(av.open(str(out/'source-audio.mp4')).decode(video=0)):
        if frame_index not in selected:continue
        raw=frame.to_ndarray(format='bgr24')
        def compose(layers):
            image=raw.copy()
            for layer in layers:
                name=layer['analysis_id'].removeprefix('controlled-')
                assert name in RECTS, name
                x0,y0,x1,y1=RECTS[name]
                for r in layer['mask_regions']:
                    if not r['start']<=frame_index<r['end']:continue
                    if name=='auto' and 'face' in r['targets']:
                        box=(float(x0),float(y0),float(x1),float(y1),.99,16)
                        apply_masks(image,[box],r['strength'],r['style'],context=[box],face_shape=r['faceShape'])
                    elif name!='auto' and 'custom' in r['targets']:
                        mask=np.zeros((240,320),np.uint8);mask[y0:y1,x0:x1]=1
                        apply_custom(image,mask,r['strength'],r['style'])
            return image
        image=compose(payload);reversed_image=compose(list(reversed(payload)))
        name='reference-'+str(frame_index)+'.png';Image.fromarray(image[:,:,::-1]).save(out/name)
        import cv2
        ok,jpeg=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,88]);assert ok
        Image.fromarray(cv2.imdecode(jpeg,1)[:,:,::-1]).save(out/('reference-jpeg-'+str(frame_index)+'.png'))
        if 60<=frame_index<100:
            x0,y0,x1,y1=ROIS['a_b'];delta=float(np.abs(image[y0:y1,x0:x1].astype(float)-reversed_image[y0:y1,x0:x1]).mean())
            order.append({'frame':frame_index,'a_b_reversed_mae':delta})
        rules.append({'frame':frame_index,'reference_png':name,'roi_mae_limits':{roi:12 for roi in ROIS}})
    assert len(rules)==len(selected)
    assert order and max(x['a_b_reversed_mae'] for x in order)>2, 'Fixture cannot distinguish order; choose stronger noncommutative effects'
    (out/'reference-order.json').write_text(json.dumps({'scope':'independent compositor with shared single-mask primitives','order':order,'mae_limit':12,'note':'Bounded lossy codec tolerance; retain measured errors; no endpoint self-reference'},indent=2),encoding='utf-8')
    return rules
