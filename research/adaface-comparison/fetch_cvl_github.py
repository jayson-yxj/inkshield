from pathlib import Path
import httpx,json,base64,concurrent.futures,hashlib
root=Path(__file__).resolve().parent
url='https://api.github.com/repos/mk-minchul/CVLface/git/trees/main?recursive=1'
r=httpx.get(url,timeout=25);r.raise_for_status();j=r.json();(root/'cvlface-tree.json').write_text(json.dumps(j),encoding='utf8')
names=[x['path'] for x in j['tree'] if x['path'].endswith(('iresnet/model.py','iresnet/__init__.py'))]
def f(name):
 u='https://api.github.com/repos/mk-minchul/CVLface/contents/'+name
 r=httpx.get(u,timeout=25);r.raise_for_status();j=r.json();data=base64.b64decode(j['content']);p=root/'cvlface-github'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);print(name,hashlib.sha256(data).hexdigest(),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:list(e.map(f,names))
