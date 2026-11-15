from pathlib import Path
import httpx,hashlib,json,base64,concurrent.futures
root=Path(__file__).resolve().parent
names=['README.md','inference.py','net.py','LICENSE','face_alignment/align.py','face_alignment/mtcnn.py']
def fetch(name):
 url='https://api.github.com/repos/mk-minchul/AdaFace/contents/'+name
 rec={'name':name,'url':url}
 try:
  r=httpx.get(url,timeout=30);r.raise_for_status();j=r.json();data=base64.b64decode(j['content']);p=root/'official'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);rec.update(git_blob_sha=j['sha'],sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),download_url=j['download_url'])
 except Exception as e:rec['error']=repr(e)
 print(rec,flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e:recs=list(e.map(fetch,names))
(root/'official-provenance.json').write_text(json.dumps(recs,indent=2),encoding='utf8')
