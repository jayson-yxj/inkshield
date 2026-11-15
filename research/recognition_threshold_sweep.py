"""Sensitivity only: no chosen threshold or accuracy without human truth."""
import argparse,json,collections
from pathlib import Path
import numpy as np
from identity_gallery import IdentityGallery
p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('outputs',type=Path,nargs='+');a=p.parse_args();meta=json.loads((a.cache/'cache.json').read_text())
for output in a.outputs:
 vectors=np.load(output/'embeddings.npy');results=[]
 # Coordinated enrollment/update thresholds are unchanged; only official-match cutoff varied.
 for threshold in [.4,.45,.5,.55,.6]:
  g=IdentityGallery(threshold=threshold);pending=0;ids=collections.Counter()
  for row in meta['rows']:
   faces=row['faces'];q=[f['score']>=.70 and min(f['box'][2]-f['box'][0],f['box'][3]-f['box'][1])>=40 for f in faces]
   matched=g.update([vectors[f['crop']] for f in faces],q);pending+=sum(m['person'] is None for m in matched);ids.update(m['person'] for m in matched if m['person'] is not None)
  results.append({'threshold':threshold,'candidate_ids':len(ids),'pending':pending,'assigned':sum(ids.values())})
 (output/'threshold-sweep.json').write_text(json.dumps({'note':'Sensitivity of fixed gallery; not calibrated or accuracy; enrollment/update gates remain fixed.','results':results},indent=2));print(output.name,results,flush=True)
