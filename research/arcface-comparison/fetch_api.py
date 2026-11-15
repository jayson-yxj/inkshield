from pathlib import Path
import httpx,json,hashlib,base64,zipfile
root=Path(__file__).resolve().parent
with httpx.Client(follow_redirects=True,timeout=60) as c:
 r=c.get('https://api.github.com/repos/deepinsight/insightface/contents/model_zoo/README.md');r.raise_for_status();(root/'model-zoo.md').write_bytes(base64.b64decode(r.json()['content']))
 r=c.get('https://api.github.com/repos/deepinsight/insightface/releases/tags/v0.7');r.raise_for_status();assets=r.json()['assets'];a=next(a for a in assets if a['name']=='buffalo_l.zip');(root/'release-asset.json').write_text(json.dumps(a,indent=2));print('ASSET',a['url'],flush=True)
 url=a['url']+'?download=1'
 with c.stream('GET',url,headers={'Accept':'application/octet-stream'}) as r:
  r.raise_for_status();print('RESPONSE',r.status_code,r.headers.get('content-type'),str(r.url)[:180],flush=True)
  with (root/'buffalo_l.zip.partial').open('wb') as f:
   for chunk in r.iter_bytes():f.write(chunk)
 p=root/'buffalo_l.zip.partial'
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  n=next(n for n in z.namelist() if Path(n).name=='w600k_r50.onnx');data=z.read(n);(root/'w600k_r50.onnx').write_bytes(data)
 p.replace(root/'buffalo_l.zip')
 rec={'source':a['browser_download_url'],'api_asset':a['url'],'model':'w600k_r50.onnx','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()};(root/'provenance.json').write_text(json.dumps(rec,indent=2));print(rec,flush=True)
