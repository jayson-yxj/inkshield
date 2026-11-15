"""Geometric pseudo-pair diagnostics; NOT human identity ground truth."""
import argparse,json
from pathlib import Path
import numpy as np
from summarize_identity_trial import iou
p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('outputs',type=Path,nargs='+');a=p.parse_args()
meta=json.loads((a.cache/'cache.json').read_text());within=[];adjacent=[];previous=[]
for row in meta['rows']:
 faces=row['faces']
 for i,x in enumerate(faces):
  for y in faces[i+1:]:
   if iou(x['box'],y['box'])<.05:within.append((x['crop'],y['crop']))
 # Restrict to one-to-one, very high overlap consecutive faces. Still not truth.
 candidates=sorted(((iou(x['box'],y['box']),i,j) for i,x in enumerate(previous) for j,y in enumerate(faces)),reverse=True);aa=set();bb=set()
 for score,i,j in candidates:
  if score<.9:break
  if i in aa or j in bb:continue
  aa.add(i);bb.add(j);adjacent.append((previous[i]['crop'],faces[j]['crop']))
 previous=faces
for output in a.outputs:
 vectors=np.load(output/'embeddings.npy');report=json.loads((output/'report.json').read_text());result={'model':report['pack'],'warning':'Same-frame nonoverlap presumed different; adjacent IoU>=.9 presumed same. No manual labels, cross-shot or pose verification. NOT accuracy.'}
 for label,pairs in [('same_frame_nonoverlap',within),('adjacent_high_overlap',adjacent)]:
  scores=np.array([float(vectors[i]@vectors[j]) for i,j in pairs]);result[label]={'pairs':len(pairs),'cosine_percentiles':dict(zip(['p1','p5','p50','p95','p99'],np.percentile(scores,[1,5,50,95,99]).tolist())),'fraction_ge_0.5':float(np.mean(scores>=.5))}
 (output/'pair-diagnostics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
