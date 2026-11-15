"""Add independently checked run provenance after inference; do not alter results."""
from pathlib import Path
import json,hashlib
root=Path('runtime');cache=root/'recognition-comparison-cache-v2';meta=json.loads((cache/'cache.json').read_text());policy=Path('research/identity_gallery.py');digest=hashlib.sha256(policy.read_bytes()).hexdigest()
for name in ['recognition-mobileface','recognition-arcface-r50','recognition-adaface-ir50']:
 p=root/name/'report.json';r=json.loads(p.read_text());assert r['frames']==meta['frames']
 assert len(r['detections'])==len(meta['rows'])==meta['frames']
 for original,trial in zip(meta['rows'],r['detections']):
  assert original['frame']==trial['frame']
  assert [(f['crop'],f['box']) for f in original['faces']]==[(f['crop'],f['box']) for f in trial['faces']]
 r.update(video_sha256=meta['video_sha256'],cache_sha256=hashlib.sha256((cache/'cache.json').read_bytes()).hexdigest(),external_color='RGB',external_normalization='(uint8-127.5)/127.5 float32 NCHW',gallery_source_sha256=digest,gallery_settings={'threshold':.5,'margin':.1,'enroll_threshold':.4,'confirmations':5,'max_templates':6,'provisional_similarity':.65,'provisional_margin':.1,'update_score':.6,'update_margin':.15,'anchor_min':.45,'novelty_max':.9,'min_detection_score':.7,'min_face_px':40},artifact_retention='Local aligned crops and embeddings saved for reproducible diagnostics, no upload or production distribution')
 p.write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8');print('PROVENANCE',name,'all frame/crop/boxes verified')
