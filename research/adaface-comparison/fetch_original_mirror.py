from pathlib import Path
import httpx,hashlib,json
root=Path(__file__).resolve().parent
url='https://hf-mirror.com/Jaspann/Person-Recognition-for-Pose-Estimation/resolve/main/components/adaface_ir50_ms1mv2.ckpt?download=true'
rec={'url':url,'provenance_caution':'Third-party mirror of original author-named checkpoint, not independently author checksum authenticated.'}
try:
 h=hashlib.sha256();n=0
 with httpx.stream('GET',url,follow_redirects=True,timeout=40) as r:
  rec.update(status=r.status_code);r.raise_for_status()
  with (root/'adaface_ir50_ms1mv2.ckpt').open('wb') as f:
   for b in r.iter_bytes():f.write(b);h.update(b);n+=len(b)
 rec.update(bytes=n,sha256=h.hexdigest());assert h.hexdigest()=='234da6ce931f821e0a8e920063dc2091d8122ea46285c159d2f25d3f762fecb3'
except Exception as e:rec['error']=repr(e)
(root/'original-mirror-provenance.json').write_text(json.dumps(rec,indent=2),encoding='utf8');print(rec)
