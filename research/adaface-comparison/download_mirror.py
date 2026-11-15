from pathlib import Path
import httpx,json,hashlib,concurrent.futures
root=Path(__file__).resolve().parent
urls={
'original-mirror-tree.json':'https://hf-mirror.com/api/models/Jaspann/Person-Recognition-for-Pose-Estimation/tree/main?recursive=true',
'author-model.safetensors':'https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/resolve/main/model.safetensors?download=true',
'author-iresnet.py':'https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/raw/main/models/iresnet/model.py',
'author-wrapper.py':'https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/raw/main/wrapper.py',
}
def fetch(k,u):
 rec={'name':k,'url':u};h=hashlib.sha256();size=0
 try:
  with httpx.stream('GET',u,timeout=40,follow_redirects=True) as r:
   rec.update(status=r.status_code,final_url=str(r.url));r.raise_for_status()
   with (root/k).open('wb') as f:
    for chunk in r.iter_bytes():f.write(chunk);h.update(chunk);size+=len(chunk)
   rec.update(bytes=size,sha256=h.hexdigest())
 except Exception as e:rec['error']=repr(e)
 print(rec,flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:recs=list(e.map(lambda kv:fetch(*kv),urls.items()))
(root/'mirror-download-provenance.json').write_text(json.dumps(recs,indent=2),encoding='utf8')
