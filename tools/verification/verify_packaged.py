"""Verify a running desktop.py/EXE through its per-process state file."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import argparse,json,time
from pathlib import Path
import cv2,httpx

p=argparse.ArgumentParser();p.add_argument('state');p.add_argument('--require-frozen',action='store_true');args=p.parse_args()
s=json.loads(Path(args.state).read_text(encoding='utf-8'))
if args.require_frozen:assert s['frozen'],s
base=s['url'];root=Path(__file__).resolve().parents[2]

def wait(c,job,done):
 deadline=time.monotonic()+180
 while time.monotonic()<deadline:
  status=c.get('/api/status/'+job).json()
  assert status['state']!='error',status
  if status['state']==done:return status
  time.sleep(.1)
 raise AssertionError('Timed out')

report={'frozen':s['frozen'],'url':base,'data_dir':s['data_dir'],'segments':[]}
with httpx.Client(base_url=base,timeout=180,trust_env=False) as c:
 page=c.get('/');page.raise_for_status();assert '一键分析' in page.text
 startup=c.get('/startup');startup.raise_for_status();assert startup.content==(root/'src/inkshield/web/splash-preview.html').read_bytes();assert "location.pathname==='/startup'" in startup.text
 health=c.get('/api/health');health.raise_for_status();assert health.json()['model_ready'],health.text
 with (root/'runtime/plate-real-input.mp4').open('rb') as f:
  r=c.post('/api/media',files={'video':('验证素材.mp4',f,'video/mp4')})
 r.raise_for_status();media=r.json()
 for start,end in ((0,3),(3,8)):
  r=c.post('/api/analyze',data={'media_id':media['media_id'],'start_frame':start,'end_frame':end});r.raise_for_status()
  job=r.json()['job_id'];status=wait(c,job,'ready')
  assert status['frames']==end-start and status['threshold']==.5,status
  cache=Path(s['data_dir'])/'runtime'/job/'detections.json';assert cache.is_file(),cache
  payload=c.get('/api/playback/'+job).json();assert payload['start_frame']==start and payload['frames']==end-start
  for style in ('mosaic','blur','black'):
   r=c.get('/api/preview/'+job,params={'frame':end-start-1,'target':'face,plate','style':style});r.raise_for_status();assert r.headers['content-type'].startswith('image/jpeg')
  r=c.get('/api/preview/'+job,params={'frame':end-start});assert r.status_code==422
  r=c.post('/api/export/'+job,data={'target':'plate','style':'black'});r.raise_for_status()
  output_status=wait(c,r.json()['job_id'],'done');output=c.get(output_status['download']);output.raise_for_status()
  path=Path(s['data_dir'])/f'verified-{start}-{end}.mp4';path.write_bytes(output.content)
  cap=cv2.VideoCapture(str(path));count=0
  while True:
   ok,frame=cap.read()
   if not ok:break
   count+=1
  cap.release();assert count==end-start,(count,start,end)
  report['segments'].append({'start':start,'end':end,'decoded_export_frames':count,'cpu_mode':status.get('cpu_mode'),'analysis_seconds':status['analysis_seconds'],'timing_ms':status.get('timing_ms')})
path=Path(s['data_dir'])/'packaged-verification.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2));print('DESKTOP/PACKAGED HTTP FLOW PASS')
