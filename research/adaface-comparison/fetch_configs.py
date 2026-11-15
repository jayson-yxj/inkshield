from pathlib import Path
import httpx,json,concurrent.futures
root=Path(__file__).resolve().parent
names=['pretrained_model/config.yaml','pretrained_model/model.yaml','config.json','wrapper.py','models/iresnet/__init__.py']
def f(name):
 u='https://hf-mirror.com/minchul/cvlface_adaface_ir50_ms1mv2/raw/aa35c74e86afb7482cb7859af4c14eab83a8728d/'+name
 try:
  r=httpx.get(u,timeout=15,follow_redirects=True);r.raise_for_status();p=root/'cvlface-author'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.content);print(name,r.text[:250],flush=True)
 except Exception as e:print(name,repr(e),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as e:list(e.map(f,names))
