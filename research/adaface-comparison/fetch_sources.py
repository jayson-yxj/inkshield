from pathlib import Path
import httpx, hashlib, json
root=Path(__file__).resolve().parent
base='https://raw.githubusercontent.com/mk-minchul/AdaFace/master/'
records=[]
for name in ['README.md','inference.py','net.py','LICENSE','face_alignment/align.py','face_alignment/mtcnn.py']:
    r={'name':name,'url':base+name}
    try:
        resp=httpx.get(r['url'],follow_redirects=True,timeout=35);resp.raise_for_status()
        p=root/'official'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(resp.content)
        r.update(status=resp.status_code,bytes=len(resp.content),sha256=hashlib.sha256(resp.content).hexdigest())
    except Exception as e:r['error']=repr(e)
    records.append(r);print(r,flush=True)
(root/'source-provenance.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
