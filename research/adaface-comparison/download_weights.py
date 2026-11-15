from pathlib import Path
import httpx,json,hashlib,time
root=Path(__file__).resolve().parent
urls=[
 'https://drive.usercontent.google.com/download?id=1eUaSHG4pGlIZK7hBkqjyp2fc2epKoBvI&export=download&confirm=t',
 'https://drive.google.com/uc?export=download&id=1eUaSHG4pGlIZK7hBkqjyp2fc2epKoBvI&confirm=t',
]
recs=[]
for url in urls:
 rec={'url':url,'started':time.time()}
 try:
  with httpx.stream('GET',url,timeout=40,follow_redirects=True) as r:
   rec.update(status=r.status_code,headers=dict(r.headers),final_url=str(r.url));r.raise_for_status()
   p=root/'adaface_ir50_ms1mv2.ckpt';h=hashlib.sha256();size=0
   with p.open('wb') as f:
    for chunk in r.iter_bytes():f.write(chunk);h.update(chunk);size+=len(chunk)
   rec.update(bytes=size,sha256=h.hexdigest()); print(rec,flush=True)
   if size>10000000:recs.append(rec);break
 except Exception as e:rec['error']=repr(e);print(rec,flush=True)
 recs.append(rec)
(root/'weights-provenance.json').write_text(json.dumps(recs,indent=2),encoding='utf8')
