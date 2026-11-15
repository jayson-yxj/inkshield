"""Verify every supported mask has fractional edge alpha for every style."""
import math
import cv2
import numpy as np
import masking

rng=np.random.default_rng(12)
source=rng.integers(0,256,(200,240,3),dtype=np.uint8)
for cls in (7,16,17,18,19,20,21):
    boxes=[(65,65,155,115,.9,cls)]
    contexts=boxes
    cases=[(boxes,contexts)]
    if cls==17:
        eyes=[(70,75,100,95,.9,17),(120,88,150,108,.9,17)]
        cases.append((eyes,[(40,40,180,160,.9,7)]+eyes))
    for regions,context in cases:
        kind,cx,cy,rx,ry,angle=masking.build_shapes(regions,context)[0]
        c,s=math.cos(angle),math.sin(angle)
        ex,ey=abs(c)*rx+abs(s)*ry,abs(s)*rx+abs(c)*ry
        x0,y0=max(0,math.floor(cx-ex)),max(0,math.floor(cy-ey))
        x1,y1=min(240,math.ceil(cx+ex)),min(200,math.ceil(cy+ey))
        yy,xx=np.ogrid[y0:y1,x0:x1]
        u=(xx+.5-cx)*c+(yy+.5-cy)*s;v=-(xx+.5-cx)*s+(yy+.5-cy)*c
        if kind=='ellipse':t=np.clip((1-np.sqrt((u/rx)**2+(v/ry)**2))/.2,0,1)
        else:t=np.clip(np.minimum(rx-abs(u),ry-abs(v))/(.2*min(rx,ry)),0,1)
        alpha=(t*t*(3-2*t))[...,None]
        edge=(alpha[:,:,0]>.1)&(alpha[:,:,0]<.9)
        assert edge.sum()>10,(cls,kind)
        original=source[y0:y1,x0:x1].copy()
        for style in ('black','blur','mosaic'):
            if style=='black':effect=np.zeros_like(original)
            elif style=='blur':
                sigma=max(2.,min(2*rx,2*ry)*(.08+68*.003))
                effect=cv2.GaussianBlur(original,(0,0),sigmaX=sigma,sigmaY=sigma,borderType=cv2.BORDER_REPLICATE)
            else:
                blocks=max(4,int(24-68*.18));h,w=original.shape[:2]
                sw=max(1,min(w//2,blocks));sh=max(1,min(h//2,round(blocks*h/w)))
                effect=cv2.resize(cv2.resize(original,(sw,sh),interpolation=cv2.INTER_AREA),(w,h),interpolation=cv2.INTER_NEAREST)
            expected=np.rint(original*(1-alpha)+effect*alpha).clip(0,255).astype(np.uint8)
            output=source.copy();masking.apply_masks(output,regions,68,style,context)
            actual=output[y0:y1,x0:x1]
            assert np.array_equal(actual,expected),(cls,kind,style)
            assert np.any((actual[edge]!=original[edge])&(actual[edge]!=effect[edge])),(cls,style)
print('FEATHER PASS: all 7 classes, single/paired eyes, 3 styles; fractional edge blend matches smoothstep, no hard-edge bypass')
