"""Verify complete comparison artifacts, not recognition accuracy."""
from pathlib import Path
import base64, hashlib, json, re
import cv2
import numpy as np
root = Path('runtime')
review = root / 'recognition-three-model-review'
summary = json.loads((review / 'summary.json').read_text())
cache = json.loads((root / 'recognition-comparison-cache-v2/cache.json').read_text())
assert summary['frames'] == summary['decoded_comparison_frames'] == cache['frames'] == 6454
assert [m['model'] for m in summary['models']] == ['MobileFaceNet','ArcFace-ResNet50','AdaFace-IR50']
for name, measured in zip(['recognition-mobileface', 'recognition-arcface-r50', 'recognition-adaface-ir50'], summary['models']):
    folder = root / name
    r = json.loads((folder / 'report.json').read_text())
    vectors = np.load(folder / 'embeddings.npy', mmap_mode='r')
    assert vectors.shape == (cache['crops'], 512)
    assert np.isfinite(vectors).all()
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    assert measured['model'] == r['pack']
    identities_all = [f['person'] for row in r['detections'] for f in row['faces']]
    assert measured['assigned'] == sum(pid is not None for pid in identities_all)
    assert measured['pending'] == sum(pid is None for pid in identities_all)
    assert measured['candidate_ids'] == len({pid for pid in identities_all if pid is not None})
    assert measured['assigned'] + measured['pending'] == cache['crops'] == 11383
    assert r['video_sha256'] == cache['video_sha256']
    assert len(r['detections']) == cache['frames']
    assert max(r['templates_per_person']) <= 6
    for frame in r['detections']:
        identities = [f['person'] for f in frame['faces'] if f['person'] is not None]
        assert len(identities) == len(set(identities))
page = (review / '人物核对.html').read_text(encoding='utf-8')
assert page.count('<section>') == 3 and page.count('待确认样本（可能包含多人）') == 3
images = re.findall(r'data:image/jpeg;base64,([^\"]+)', page)
assert images
for image in images:
    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(image), dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None and decoded.shape == (112,112,3)
files = []
for name in ['comparison.mp4', '人物核对.html', '测试报告.md', 'summary.json']:
    path = review / name
    assert path.is_file() and path.stat().st_size > 0
    files.append({'file':name, 'bytes':path.stat().st_size, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
result = {'status':'verified', 'frames':6454, 'faces':11383, 'embedded_review_images':len(images), 'files':files, 'scope':'Integrity and structural checks only; no visual or human identity accuracy verification'}
(review / 'delivery-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
