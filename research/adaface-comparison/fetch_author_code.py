from pathlib import Path
import httpx,json,base64,hashlib,concurrent.futures
root=Path(__file__).resolve().parent
j=json.loads((root/'hfmirror-files.txt').read_text());names=[x['path'] for x in j if x['type']=='file' and not x['path'].endswith('.safetensors')]
def f(name):
 rec={'name':name};p=root/'cvlface-author'/name;p.parent.mkdir(parents=True,exist_ok=True)
 # Resolve endpoint rather than raw (the mirror supports resolve more reliably).
 url='https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/resolve/main/'+name;rec['url']=url
 try:
  r=httpx.get(url,timeout=25,follow_redirects=True);r.raise_for_status();p.write_bytes(r.content);rec.update(bytes=len(r.content),sha256=hashlib.sha256(r.content).hexdigest())
 except Exception as e:rec['error']=repr(e)
 print(rec,flush=True);return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as e:records=list(e.map(f,names))
(root/'author-code-provenance.json').write_text(json.dumps(records,indent=2),encoding='utf8')
