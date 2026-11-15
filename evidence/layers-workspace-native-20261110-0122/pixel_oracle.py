"""Compare decoded output to independently prepared frame PNG references.
Reference construction and codec tolerances must be reviewed at freeze. Never
use the endpoint under test as its own reference. Save raw ROI errors.
"""
from pathlib import Path
import av, numpy as np
from PIL import Image
from controlled_fixtures import ROIS

def validate_asset(path, asset, out):
    expected = asset.get('pixel_expectations', [])
    assert expected, 'Missing independent pixel expectations: '+asset['name']
    by_frame = {int(e['frame']):e for e in expected}
    assert len(by_frame)==len(expected), 'Duplicate pixel reference frame'
    checks=[]
    with av.open(str(path)) as container:
        for i,frame in enumerate(container.decode(video=0)):
            if i not in by_frame: continue
            rule = by_frame.pop(i)
            ref = (out / rule['reference_png']).resolve()
            assert ref.is_relative_to(out.resolve()), 'Reference must be owned evidence'
            actual=frame.to_ndarray(format='rgb24').astype(np.float32)
            target=np.asarray(Image.open(ref).convert('RGB'),dtype=np.float32)
            assert actual.shape==target.shape==(240,320,3)
            for roi,limit in rule['roi_mae_limits'].items():
                x0,y0,x1,y1=ROIS[roi]
                mae=float(np.abs(actual[y0:y1,x0:x1]-target[y0:y1,x0:x1]).mean())
                checks.append({'frame':i,'roi':roi,'mae':mae,'limit':limit,'passed':mae<=limit})
    assert not by_frame, 'Missing decoded reference frames'
    assert checks and all(c['passed'] for c in checks), checks
    return {'asset':asset['name'],'checks':checks}
