"""Isolated real-GPU middle-anchor evidence; no HTTP service or production state."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
os.environ['INKSHIELD_SAM_VENDOR'] = str(ROOT/'research/sam21-prototype/vendor/sam2')
os.environ['INKSHIELD_SAM_MODEL'] = str(ROOT/'models/sam2.1_hiera_tiny.pt')

import cv2
import numpy as np
from inkshield.sam_engine import SamEngine


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT/'runtime/sam-middle-anchor-gpu-evidence'
    frames = output/'frames'
    frames.mkdir(parents=True, exist_ok=True)
    truths = []
    for idx in range(7):
        image = np.full((192,320,3), (45,65,85), np.uint8)
        # A stable textured object moves slowly; both boundaries contain it.
        center = (130+idx*5,96)
        cv2.circle(image, center, 34, (25,160,230), -1)
        cv2.circle(image, (center[0]-10,85), 8, (50,200,255), -1)
        cv2.ellipse(image, (center[0]+9,108), (10,7), 20,0,360,(15,95,160),-1)
        ok, encoded = cv2.imencode('.jpg',image)
        assert ok
        (frames/f'{idx:05d}.jpg').write_bytes(encoded.tobytes())
        truth = np.zeros((192,320),np.uint8)
        cv2.circle(truth,center,34,1,-1)
        truths.append(truth)
    engine = SamEngine('cuda')
    predictor = engine._load()
    original = predictor.propagate_in_video
    calls = []
    def tracked(*args, **kwargs):
        calls.append(dict(kwargs))
        yield from original(*args, **kwargs)
    predictor.propagate_in_video = tracked
    cases = []
    for anchors in ([3],[5,2]):
        calls.clear()
        prompts = {i:[{'x':130+i*5,'y':96,'label':1}] for i in anchors}
        started = time.perf_counter()
        masks,timing = engine.segment(frames,prompts,7)
        rows = []
        for idx in range(7):
            mask=masks[idx]
            intersection=int(np.count_nonzero((mask>0)&(truths[idx]>0)))
            union=int(np.count_nonzero((mask>0)|(truths[idx]>0)))
            rows.append({'frame':idx,'area':int(mask.sum()),'iou':intersection/union})
            cv2.imwrite(str(output/f'anchors-{"-".join(map(str,anchors))}-mask-{idx}.png'),mask*255)
        assert len(masks)==7 and all(row['area']>0 for row in rows), rows
        assert min(row['iou'] for row in rows)>.85, rows
        cases.append({'anchors':anchors,'calls':list(calls),'masks':rows,'seconds':time.perf_counter()-started,'timing':timing})
    import torch
    report={'device':torch.cuda.get_device_name(),'torch':torch.__version__,
            'model_sha256':digest(Path(os.environ['INKSHIELD_SAM_MODEL'])),
            'source_sha256':{str(path.relative_to(ROOT)):digest(path) for path in
                (ROOT/'src/inkshield/sam_engine.py',ROOT/'src/inkshield/sam_service.py',ROOT/'tests/integration/test_sam_propagation.py',
                 ROOT/'research/sam21-prototype/vendor/sam2/sam2/sam2_video_predictor.py')},
            'fixture_sha256':{p.name:digest(p) for p in frames.glob('*.jpg')},'cases':cases}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
