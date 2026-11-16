"""Exercise the running HTTP service, not an in-process app."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import time
import httpx
from pathlib import Path

with httpx.Client(base_url='http://127.0.0.1:8001',timeout=120,trust_env=False) as c:
    health=c.get('/api/health');health.raise_for_status()
    assert 'plate' in health.json()['targets']
    assert c.get('/openapi.json').json()['info']['version']=='0.10.0'
    page=c.get('/');page.raise_for_status();assert 'data-value="plate"' in page.text
    with Path('runtime/plate-real-input.mp4').open('rb') as f:
        r=c.post('/api/analyze',files={'video':('clip.mp4',f,'video/mp4')})
    r.raise_for_status()
    job=r.json()['job_id']
    deadline=time.monotonic()+120
    while True:
        s=c.get('/api/status/'+job).json()
        assert s['state']!='error',s
        if s['state']=='ready':break
        assert time.monotonic()<deadline
        time.sleep(.1)
    playback=c.get('/api/playback/'+job);playback.raise_for_status()
    data=playback.json()
    assert data['frames']==s['frames'] and len(data['shapes'])==s['frames']
    assert all(any(shape[-1]==21 for shape in row) for row in data['shapes'])
    print('LIVE playback geometry PASS',data['frames'],'frames',len(playback.content),'bytes',flush=True)
    for target in ('plate','head,plate','eyes,mouth,plate'):
        t=time.perf_counter()
        r=c.get('/api/preview/'+job,params={'target':target,'style':'black','frame':s['frames']-1})
        r.raise_for_status()
        print('preview',target,round((time.perf_counter()-t)*1000,1),'ms',len(r.content),flush=True)
    r=c.post('/api/export/'+job,data={'target':'plate','style':'black'})
    r.raise_for_status()
    export_id=r.json()['job_id']
    while True:
        e=c.get('/api/status/'+export_id).json()
        assert e['state']!='error',e
        if e['state']=='done':break
        assert time.monotonic()<deadline
        time.sleep(.1)
    r=c.get(e['download']);r.raise_for_status()
    print('LIVE cached export PASS',e, 'bytes',len(r.content),flush=True)
