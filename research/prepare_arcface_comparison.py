"""Fetch official research weights; production dependencies untouched."""
from pathlib import Path
import httpx,json,hashlib,zipfile,time
root=Path(__file__).resolve().parent/'arcface-comparison';root.mkdir(exist_ok=True)
urls={'model-zoo.md':'https://raw.githubusercontent.com/deepinsight/insightface/master/model_zoo/README.md','buffalo_l.zip':'https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip'}
records=[]
for name,url in urls.items():
 p=root/name
 for attempt in range(3):
  try:
   if not p.exists():
    with httpx.stream('GET',url,follow_redirects=True,timeout=120) as r:
     r.raise_for_status()
     with p.with_suffix(p.suffix+'.partial').open('wb') as f:
      for chunk in r.iter_bytes():f.write(chunk)
    p.with_suffix(p.suffix+'.partial').replace(p)
   rec={'name':name,'url':url,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};records.append(rec);print(rec,flush=True);break
  except Exception as e:
   print(name,attempt,type(e).__name__,str(e),flush=True)
   if attempt==2:raise
with zipfile.ZipFile(root/'buffalo_l.zip') as z:
 assert z.testzip() is None
 names=[n for n in z.namelist() if Path(n).name=='w600k_r50.onnx'];assert len(names)==1,z.namelist()
 data=z.read(names[0]);p=root/'w600k_r50.onnx';p.write_bytes(data)
 records.append({'name':p.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'source':'official buffalo_l.zip'})
(root/'provenance.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print('READY',records[-1],flush=True)
