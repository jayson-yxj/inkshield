"""Actual HTTP metadata/manual segment analysis/cached export smoke check."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import time
from pathlib import Path
import cv2
import httpx

def wait(c,job,done):
 deadline=time.monotonic()+120
 while True:
  s=c.get('/api/status/'+job).json()
  assert s['state']!='error',s
  if s['state']==done:return s
  assert time.monotonic()<deadline,s
  time.sleep(.05)

with httpx.Client(base_url='http://127.0.0.1:8001',timeout=120,trust_env=False) as c:
 assert c.get('/openapi.json').json()['info']['version']=='0.10.0'
 page=c.get('/');page.raise_for_status();assert '一键分析' in page.text
 with Path('runtime/plate-real-input.mp4').open('rb') as f:
  r=c.post('/api/media',files={'video':('clip.mp4',f,'video/mp4')})
 r.raise_for_status();media=r.json();assert media['frames']>=8,media
 for start,end in ((0,3),(3,8)):
  r=c.post('/api/analyze',data={'media_id':media['media_id'],'start_frame':start,'end_frame':end})
  r.raise_for_status();job=r.json()['job_id'];s=wait(c,job,'ready')
  assert s['frames']==end-start and s['threshold']==.5,s
  p=c.get('/api/playback/'+job);p.raise_for_status();d=p.json()
  assert d['start_frame']==start and d['frames']==end-start,d
  r=c.get('/api/preview/'+job,params={'frame':end-start-1,'target':'plate','style':'black'});r.raise_for_status()
  r=c.get('/api/preview/'+job,params={'frame':end-start,'target':'plate'});assert r.status_code==422
  r=c.post('/api/export/'+job,data={'target':'plate','style':'black'});r.raise_for_status()
  e=wait(c,r.json()['job_id'],'done');r=c.get(e['download']);r.raise_for_status()
  output=Path('runtime')/f'live-segment-{start}-{end}.mp4';output.write_bytes(r.content)
  cap=cv2.VideoCapture(str(output));count=0
  while True:
   ok,frame=cap.read()
   if not ok:break
   count+=1
  cap.release();assert count==end-start,(start,end,count)
  print('LIVE SEGMENT PASS',start,end,'frames',count,'threshold',s['threshold'])
 print('LIVE MEDIA/MANUAL ANALYSIS/SEGMENT PREVIEW/EXPORT PASS')
