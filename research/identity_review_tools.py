"""Rebuild enrollment thumbnails and compare identity trial reports."""
import argparse
import collections
import json
from pathlib import Path
import cv2

p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('directory',type=Path);args=p.parse_args()
data=json.loads((args.directory/'report.json').read_text(encoding='utf-8'))
enroll={r['frame']:[f for f in r['faces'] if f['status']=='enrolled'] for r in data['detections']}
enroll={k:v for k,v in enroll.items() if v}
cap=cv2.VideoCapture(args.video)
for frame,faces in enroll.items():
    cap.set(cv2.CAP_PROP_POS_FRAMES,frame);ok,image=cap.read()
    if not ok:raise RuntimeError(f'Cannot decode enrollment frame {frame}')
    h,w=image.shape[:2]
    for face in faces:
        x0,y0,x1,y1=map(int,face['box']);crop=image[max(0,y0):min(h,y1),max(0,x0):min(w,x1)]
        if crop.size:cv2.imwrite(str(args.directory/f"person-{face['person']:03}.jpg"),crop)
cap.release()
print('Enrollment thumbnails regenerated using public IDs')
