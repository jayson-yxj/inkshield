"""Isolated user-video first seven frames, local anchor 3, real GPU evidence."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / "src"))
os.environ['INKSHIELD_SAM_VENDOR']=str(ROOT/'research/sam21-prototype/vendor/sam2')
os.environ['INKSHIELD_SAM_MODEL']=str(ROOT/'models/sam2.1_hiera_tiny.pt')
import cv2
import numpy as np
from inkshield.sam_engine import SamEngine


def main():
    output=ROOT/'runtime/sam-middle-anchor-real-evidence'
    frames=output/'frames'
    source=Path(r'C:\Users\36301\Desktop\5.mp4')
    engine=SamEngine('cuda')
    predictor=engine._load()
    original=predictor.propagate_in_video
    calls=[]
    def tracked(*args,**kwargs):
        calls.append(dict(kwargs))
        yield from original(*args,**kwargs)
    predictor.propagate_in_video=tracked
    # Coordinates supplied in the earlier real-video preview acceptance request.
    point={'x':646,'y':218,'label':1}
    masks,timing=engine.segment(frames,{3:[point]},7)
    rows=[]
    for idx,mask in sorted(masks.items()):
        ys,xs=np.nonzero(mask)
        rows.append({'frame':idx,'area':int(mask.sum()),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if xs.size else None})
        cv2.imwrite(str(output/f'mask-{idx}.png'),mask*255)
    assert set(masks)==set(range(7))
    assert all(row['area']>0 for row in rows),rows
    report={'source_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'range':[0,7],'anchor':3,'point':point,'calls':calls,'masks':rows,'timing':timing,
            'source_sha256s':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                (ROOT/'src/inkshield/sam_engine.py',ROOT/'src/inkshield/sam_service.py',ROOT/'tests/integration/test_sam_propagation.py',ROOT/'tests/integration/test_sam_integration.py')},
            'fixture_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in frames.glob('*.jpg')}}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
