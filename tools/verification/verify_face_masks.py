"""Exact selectable ellipse geometry, radial feather, styles and plate regression."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import math
import cv2
import numpy as np
from inkshield.masking import apply_masks, build_shapes

STYLES = ('mosaic','blur','black','boxblur','horizontal','vertical')
for mode, expansion in (('inscribed',1.),('circumscribed',math.sqrt(2))):
    for cls in (16,21):
        for coords in ((40,40,80,80),(0,0,15,20),(70,65,99,99),(30.1,30.1,30.2,30.2)):
            box = (*coords,.9,cls)
            kind,cx,cy,rx,ry,_ = build_shapes([box],face_shape=mode)[0]
            scale = expansion if cls == 16 else 1.25
            assert kind == ('ellipse' if cls == 16 else 'rectangle')
            assert np.isclose(rx,(coords[2]-coords[0])/2*scale)
            assert np.isclose(ry,(coords[3]-coords[1])/2*scale)
            for style in STYLES:
                original = np.random.default_rng(12).integers(0,256,(120,120,3),dtype=np.uint8)
                frame = original.copy()
                apply_masks(frame,[box],68,style,face_shape=mode)
                assert np.any(frame != original),(mode,cls,coords,style)
            if cls == 21:
                image = np.full((120,120,3),255,np.uint8)
                apply_masks(image,[box],68,'black',face_shape=mode)
                yy,xx = np.ogrid[:120,:120]
                x0,y0,x1,y1 = coords
                inside = (xx+.5>=x0)&(xx+.5<=x1)&(yy+.5>=y0)&(yy+.5<=y1)
                assert not image[inside].any()
    # Independent whole-frame alpha reference tests the ellipse boundary, opaque
    # core and feather (detector corners are not claimed to be opaque).
    box = (40,40,80,80,.9,16)
    _,cx,cy,rx,ry,_ = build_shapes([box],face_shape=mode)[0]
    assert np.isclose(math.sqrt((20/rx)**2+(20/ry)**2),math.sqrt(2)/expansion)
    yy,xx = np.ogrid[:120,:120]
    radius = np.sqrt(((xx+.5-cx)/rx)**2+((yy+.5-cy)/ry)**2)
    t = np.clip((1-radius)/.20,0,1)
    alpha = (t*t*(3-2*t))[...,None]
    original = np.random.default_rng(42).integers(0,256,(120,120,3),dtype=np.uint8)
    x0,y0,x1,y1 = math.floor(cx-rx),math.floor(cy-ry),math.ceil(cx+rx),math.ceil(cy+ry)
    crop = original[y0:y1,x0:x1]
    for strength in (20,68,100):
        for style in STYLES:
            effect = np.zeros_like(crop)
            if style == 'blur':
                sigma = max(2.,min(2*rx,2*ry)*(.08+strength*.003))
                effect = cv2.GaussianBlur(crop,(0,0),sigmaX=sigma,sigmaY=sigma,borderType=cv2.BORDER_REPLICATE)
            elif style in ('boxblur','horizontal','vertical'):
                k = max(3,round(min(2*rx,2*ry)*(.16+strength*.006))|1)
                kernel = {'boxblur':(k,k),'horizontal':(k,1),'vertical':(1,k)}[style]
                effect = cv2.blur(crop,kernel,borderType=cv2.BORDER_REPLICATE)
            elif style == 'mosaic':
                blocks = max(4,int(24-strength*.18))
                small = cv2.resize(crop,(blocks,blocks),interpolation=cv2.INTER_AREA)
                effect = cv2.resize(small,(x1-x0,y1-y0),interpolation=cv2.INTER_NEAREST)
            expected = original.copy()
            a = alpha[y0:y1,x0:x1]
            expected[y0:y1,x0:x1] = np.rint(crop*(1-a)+effect*a).clip(0,255).astype(np.uint8)
            actual = original.copy()
            apply_masks(actual,[box],strength,style,face_shape=mode)
            assert np.array_equal(actual,expected),(mode,style,strength)
            assert np.array_equal(actual[radius>=1],original[radius>=1])
            untouched = original.copy()
            apply_masks(untouched,[],strength,style,face_shape=mode)
            assert np.array_equal(untouched,original)
assert build_shapes([(0,0,10,10,.9,17)]) == []
print('MASK PASS: both exact ellipses, radial boundary/feather, plate rectangles, borders, subpixel, six styles, empty targets')
