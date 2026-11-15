from pathlib import Path
import httpx,hashlib,json,concurrent.futures
root=Path(__file__).resolve().parent
urls={
'readme-api':'https://api.github.com/repos/mk-minchul/AdaFace/contents/README.md',
'readme-cdn':'https://cdn.jsdelivr.net/gh/mk-minchul/AdaFace@master/README.md',
'net-cdn':'https://cdn.jsdelivr.net/gh/mk-minchul/AdaFace@master/net.py',
'inference-cdn':'https://cdn.jsdelivr.net/gh/mk-minchul/AdaFace@master/inference.py',
'license-cdn':'https://cdn.jsdelivr.net/gh/mk-minchul/AdaFace@master/LICENSE',
'hf-readme':'https://huggingface.co/minchul/cvlface_adaface_ir50_ms1mv2/raw/main/README.md',
'hf-files':'https://huggingface.co/api/models/minchul/cvlface_adaface_ir50_ms1mv2/tree/main?recursive=true',
}
def fetch(k,u):
 r={'name':k,'url':u}
 try:
  s=httpx.get(u,timeout=18,follow_redirects=True);s.raise_for_status();(root/(k+'.txt')).write_bytes(s.content);r.update(status=s.status_code,bytes=len(s.content),sha256=hashlib.sha256(s.content).hexdigest())
 except Exception as e:r['error']=repr(e)
 print(r,flush=True);return r
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as e: records=list(e.map(lambda kv:fetch(*kv),urls.items()))
(root/'alternate-provenance.json').write_text(json.dumps(records,indent=2),encoding='utf8')
