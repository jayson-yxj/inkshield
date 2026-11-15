"""Immutable geometry-aligned fixture analyses; no production writes or inference."""
import numpy as np
RECTS = {'auto':(25,45,145,155),'custom-a':(95,85,215,195),'custom-b':(165,45,285,155)}
# Each layer has an exclusive ROI; adjacent layers overlap, permitting order checks.
ROIS = {'face_only':[45,65,65,85], 'a_only':[125,170,145,190], 'b_only':[245,65,265,85], 'face_a':[110,100,130,120], 'a_b':[180,100,200,120], 'outside':[5,210,25,230]}
def install(server, source):
    for suffix, start, count in [('',0,150),('-head',0,140),('-tail',140,10),('-short-head',0,148),('-short-tail',148,2)]:
        for kind,(x0,y0,x1,y1) in RECTS.items():
            custom = kind != 'auto'
            mask = np.zeros((240,320),np.uint8)
            mask[y0:y1,x0:x1] = 1
            mask.flags.writeable = False
            name = 'controlled-'+kind+suffix
            boxes = tuple(() if custom else ((float(x0),float(y0),float(x1),float(y1),.99,16),) for _ in range(count))
            ids = tuple(() if custom else (None,) for _ in range(count))
            server.ANALYSES[name] = server.Analysis(input_path=source,boxes=boxes,width=320,height=240,fps=25,start_frame=start,face_ids=ids,custom_masks=tuple(mask for _ in range(count)) if custom else (),sam_device='cpu' if custom else None)
            server.JOBS[name] = {'state':'ready','kind':'analyze','frames':count,'fps':25,'width':320,'height':240,'start_frame':start,'end_frame':start+count}
