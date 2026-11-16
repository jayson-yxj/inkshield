"""Shared face/plate mask geometry in original-frame pixels."""
import math
import cv2
import numpy as np


def build_shapes(regions, context=None, face_shape='circumscribed'):
    """Selectable detector-box ellipses; plates retain their expanded rectangle."""
    if face_shape not in ('inscribed', 'circumscribed'):
        raise ValueError('未知人脸椭圆类型')
    shapes = []
    for box in regions:
        if len(box) != 6 or not np.isfinite(box).all() or int(box[5]) not in (16, 21):
            continue
        x0, y0, x1, y1 = box[:4]
        if x1 <= x0 or y1 <= y0:
            continue
        expansion = 1. if face_shape == 'inscribed' else math.sqrt(2)
        kind, expansion = ('ellipse', expansion) if int(box[5]) == 16 else ('rectangle', 1.25)
        shapes.append((kind, (x0+x1)/2, (y0+y1)/2,
                       (x1-x0)/2*expansion, (y1-y0)/2*expansion, 0.))
    return shapes


def apply_masks(frame, regions, strength, style='mosaic', context=None, face_shape='circumscribed'):
    """In-place masking using identical cached geometry for preview and export."""
    if style not in ('mosaic', 'blur', 'black', 'boxblur', 'horizontal', 'vertical'):
        raise ValueError('未知遮罩样式')
    strength = max(20, min(100, strength))
    height, width = frame.shape[:2]
    for kind, cx, cy, rx, ry, angle in build_shapes(regions, context, face_shape):
        c, s = math.cos(angle), math.sin(angle)
        dx, dy = abs(c)*rx+abs(s)*ry, abs(s)*rx+abs(c)*ry
        x0,y0 = max(0,math.floor(cx-dx)),max(0,math.floor(cy-dy))
        x1,y1 = min(width,math.ceil(cx+dx)),min(height,math.ceil(cy+dy))
        if x1 <= x0 or y1 <= y0:
            continue
        yy,xx = np.ogrid[y0:y1,x0:x1]
        u,v = (xx+.5-cx)*c+(yy+.5-cy)*s, -(xx+.5-cx)*s+(yy+.5-cy)*c
        if kind == 'ellipse':
            t = np.clip((1-np.sqrt((u/rx)**2+(v/ry)**2))/.20, 0, 1)
        else:
            edge = np.minimum(rx-np.abs(u), ry-np.abs(v))
            t = np.clip(edge / (.20*min(rx,ry)),0,1)
        alpha = (t*t*(3-2*t))[...,None]
        if not np.any(alpha > 0):
            px = min(x1-x0-1, max(0, int(cx)-x0))
            py = min(y1-y0-1, max(0, int(cy)-y0))
            alpha[py,px,0] = 1.
        crop = frame[y0:y1,x0:x1]
        original = crop.copy()
        if style == 'black' or min(2*rx,2*ry) < 8:
            effect = np.zeros_like(crop)
        elif style == 'blur':
            sigma = max(2., min(2*rx,2*ry)*(.08+strength*.003))
            effect = cv2.GaussianBlur(crop,(0,0),sigmaX=sigma,sigmaY=sigma,borderType=cv2.BORDER_REPLICATE)
        elif style in ('boxblur', 'horizontal', 'vertical'):
            k = max(3, round(min(2*rx, 2*ry)*(.16+strength*.006)) | 1)
            kernel = {'boxblur': (k, k), 'horizontal': (k, 1), 'vertical': (1, k)}[style]
            effect = cv2.blur(crop, kernel, borderType=cv2.BORDER_REPLICATE)
        else:
            blocks = max(4,int(24-strength*.18))
            sw = max(1,min(crop.shape[1]//2,blocks))
            sh = max(1,min(crop.shape[0]//2,round(blocks*crop.shape[0]/crop.shape[1])))
            small = cv2.resize(crop,(sw,sh),interpolation=cv2.INTER_AREA)
            effect = cv2.resize(small,(crop.shape[1],crop.shape[0]),interpolation=cv2.INTER_NEAREST)
        crop[:] = np.rint(original*(1-alpha)+effect*alpha).clip(0,255).astype(np.uint8)
