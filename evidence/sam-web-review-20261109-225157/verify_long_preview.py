"""Independent real-video API verification; never edits application files."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request
import urllib.error
import uuid
import cv2
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = Path(r'C:\Users\36301\Desktop\5.mp4')
state = json.loads(next((ROOT / 'runtime' / 'sam-web-review-20261109-225157-final').glob('desktop-*.json')).read_text(encoding='utf-8'))
BASE = state['url'].rstrip('/')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
report = {'state': state, 'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'source_bytes': SOURCE.stat().st_size, 'code_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['sam_service.py','sam_engine.py']}}

def call(name, path, data=None, content_type=None):
    headers = {'Content-Type': content_type} if content_type else {}
    req = urllib.request.Request(BASE+path, data=data, headers=headers)
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=600) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    (OUT/(name+'-response.json')).write_bytes(body)
    result = json.loads(body)
    report[name] = {'status':status, 'seconds':time.perf_counter()-started, 'response_file': name+'-response.json'}
    print(name, status, round(report[name]['seconds'],3), flush=True)
    return status, result

try:
    status, caps = call('capabilities','/api/sam/capabilities')
    assert status == 200 and caps['available'] and caps['default_device'] == 'cpu', caps
    boundary = 'InkshieldReview'+uuid.uuid4().hex
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="video"; filename="5.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()+SOURCE.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
    status, media = call('upload', '/api/media', data, 'multipart/form-data; boundary='+boundary)
    assert status == 200 and media['frames'] == 6454, media
    report['media'] = media
    preview = {'media_id':media['media_id'],'start_frame':0,'end_frame':6454,'device':'cpu','frame':0,'prompts':[{'x':646,'y':218,'label':1}]}
    (OUT/'preview-request.json').write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding='utf-8')
    status, result = call('preview','/api/sam/preview', json.dumps(preview).encode(),'application/json')
    assert status == 200, result
    png = base64.b64decode(result['mask'], validate=True)
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    decoded = cv2.imdecode(np.frombuffer(png,dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert decoded is not None and decoded.shape == (media['height'],media['width'],4), None if decoded is None else decoded.shape
    selected = int(np.count_nonzero(decoded[:,:,3]))
    assert selected > 0
    (OUT/'preview-mask.png').write_bytes(png)
    report['preview'].update({'png_bytes':len(png),'decoded_shape':list(decoded.shape),'alpha_nonzero':selected,'timing_ms':result.get('timing_ms'),'cache_hit':result.get('cache_hit')})
    analyze = {key:preview[key] for key in ['media_id','start_frame','end_frame','device']}
    analyze['prompts'] = {'0':preview['prompts']}
    (OUT/'analyze-request.json').write_text(json.dumps(analyze,ensure_ascii=False,indent=2),encoding='utf-8')
    status, rejection = call('analyze_long','/api/sam/analyze',json.dumps(analyze).encode(),'application/json')
    assert status == 422 and '150' in str(rejection), rejection
    report['analyze_long']['detail'] = rejection
    report['passed'] = True
except BaseException as exc:
    report['passed'] = False
    report['error'] = repr(exc)
    raise
finally:
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
