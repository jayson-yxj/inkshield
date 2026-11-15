from pathlib import Path
import httpx,json,base64
root=Path(__file__).resolve().parent
for name in ['cvlface/research/recognition/code/run_v1/models/base/__init__.py','cvlface/research/recognition/code/run_v1/models/__init__.py']:
 r=httpx.get('https://api.github.com/repos/mk-minchul/CVLface/contents/'+name,timeout=25);r.raise_for_status();j=r.json();p=root/'cvlface-github'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(j['content']));print(name)
