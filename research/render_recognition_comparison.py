"""Render shared-video comparison and summarize diagnostic counts, not accuracy."""
import argparse,json,collections
from pathlib import Path
import cv2
from summarize_identity_trial import iou

def main():
 p=argparse.ArgumentParser();p.add_argument('video',type=Path);p.add_argument('outputs',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 reports=[json.loads((d/'report.json').read_text()) for d in a.outputs];n=reports[0]['frames'];assert all(r['frames']==n for r in reports)
 a.output.mkdir(parents=True,exist_ok=False)
 import hashlib
 video_hash=hashlib.sha256(a.video.read_bytes()).hexdigest()
 assert all(r.get('video_sha256',video_hash)==video_hash for r in reports),'Video provenance mismatch'
 cap=cv2.VideoCapture(str(a.video));fps=cap.get(cv2.CAP_PROP_FPS);assert cap.isOpened()
 writer=cv2.VideoWriter(str(a.output/'comparison.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(640*len(reports),400));assert writer.isOpened()
 idx=0
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   if frame.shape[:2]!=(720,1280):raise ValueError('This reviewed comparison layout requires 1280x720 source')
   panels=[]
   for r in reports:
    canvas=cv2.resize(frame,(640,360));canvas=cv2.copyMakeBorder(canvas,40,0,0,0,cv2.BORDER_CONSTANT,value=(20,18,16))
    cv2.putText(canvas,r['pack'],(12,27),cv2.FONT_HERSHEY_SIMPLEX,.65,(235,235,235),1)
    for f in r['detections'][idx]['faces']:
     x0,y0,x1,y1=[int(v/2) for v in f['box']];y0+=40;y1+=40;pid=f['person'];c=(128,237,184) if pid is not None else (60,190,255)
     cv2.rectangle(canvas,(x0,y0),(x1,y1),c,1);cv2.putText(canvas,str(pid) if pid else '?',(x0,max(54,y0-4)),cv2.FONT_HERSHEY_SIMPLEX,.5,c,1)
    panels.append(canvas)
   import numpy as np
   writer.write(np.hstack(panels));idx+=1
 finally:cap.release();writer.release()
 assert idx==n
 check=cv2.VideoCapture(str(a.output/'comparison.mp4'));decoded=0
 while check.grab():decoded+=1
 check.release();assert decoded==n
 summaries=[]
 for r in reports:
  ids=collections.Counter();pending=0;changes=0;transitions=0;prev=[];reasons=collections.Counter()
  for row in r['detections']:
   faces=row['faces'];ids.update(f['person'] for f in faces if f['person'] is not None);pending+=sum(f['person'] is None for f in faces);reasons.update(f['reason'] for f in faces)
   pairs=sorted(((iou(x['box'],y['box']),i,j) for i,x in enumerate(prev) for j,y in enumerate(faces)),reverse=True);aa=set();bb=set()
   for score,i,j in pairs:
    if score<.7:break
    if i in aa or j in bb:continue
    aa.add(i);bb.add(j);x=prev[i]['person'];y=faces[j]['person']
    if x!=y:
     if x is None or y is None:transitions+=1
     else:changes+=1
   prev=faces
  summaries.append({'model':r['pack'],'candidate_ids':len(ids),'assigned':sum(ids.values()),'pending':pending,'pending_fraction':pending/(pending+sum(ids.values())),'adjacent_high_overlap_nonnull_changes':changes,'pending_assigned_transitions':transitions,'reason_counts':dict(reasons),'recognition_ms_median':r['recognition_ms_median'],'recognition_ms_p95':r['recognition_ms_p95'],'recognition_total_seconds':r['recognition_total_seconds']})
 result={'frames':n,'decoded_comparison_frames':decoded,'fps':fps,'models':summaries,'warning':'Same uncalibrated gallery thresholds across models. No human identity labels; counts are not recognition accuracy.'}
 (a.output/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
