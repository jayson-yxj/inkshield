from pathlib import Path
import httpx,json,concurrent.futures,hashlib
root=Path(__file__).resolve().parent
urls={
'hfmirror-files':'https://hf-mirror.com/api/models/minchul/cvlface_adaface_ir50_ms1mv2/tree/main?recursive=true',
'hfmirror-readme':'https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/raw/main/README.md',
'gh-releases':'https://api.github.com/repos/mk-minchul/AdaFace/releases',
'gh-readme-cvlface':'https://api.github.com/repos/mk-minchul/CVLface/contents/README.md',
}
def fetch(k,u):
 rec={'name':k,'url':u}
 try:
  r=httpx.get(u,timeout=20,follow_redirects=True);r.raise_for_status();(root/(k+'.txt')).write_bytes(r.content);rec.update(bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest())
 except Exception as e:rec['error']=repr(e)
 print(rec,flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:recs=list(e.map(lambda kv:fetch(*kv),urls.items()))
(root/'model-host-probes.json').write_text(json.dumps(recs,indent=2),encoding='utf8')
