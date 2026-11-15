"""Isolated InsightFace CPU identity-binding trial, never imported by production.
Uses an isolated OpenCV/ONNX Runtime adapter with official InsightFace models
under --model-root/models/<pack>. No automatic downloads permitted.
Usage: python research/insightface_trial.py clip.mp4 --output runtime/identity-trial
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np


from identity_gallery import IdentityGallery


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    parser.add_argument('--model-root',type=Path,default=Path('research/insightface-models'))
    parser.add_argument('--pack',default='buffalo_sc')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--threshold',type=float,default=.50)
    parser.add_argument('--margin',type=float,default=.10)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--annotate',action='store_true',help='Write silent video with proposed IDs for manual review')
    args=parser.parse_args()
    model_dir=args.model_root/'models'/args.pack
    models=list(model_dir.glob('*.onnx'))
    if len(models)<2:
        parser.error(f'Missing official detection + recognition ONNX models in {model_dir}; auto-download disabled')
    from insightface_cpu import FaceAnalysis
    import onnxruntime as ort
    options=ort.SessionOptions();options.intra_op_num_threads=args.threads;options.inter_op_num_threads=1
    options.add_session_config_entry('session.intra_op.allow_spinning','0')
    app=FaceAnalysis(name=args.pack,root=str(args.model_root),allowed_modules=['detection','recognition'],
                     providers=['CPUExecutionProvider'],sess_options=options)
    app.prepare(ctx_id=-1,det_size=(640,640),det_thresh=.5)
    if 'recognition' not in app.models:raise RuntimeError('Model pack has no recognition model')
    args.output.mkdir(parents=True,exist_ok=False)
    capture=cv2.VideoCapture(str(args.video));fps=capture.get(cv2.CAP_PROP_FPS)
    if not capture.isOpened() or fps<=0:raise RuntimeError('Cannot open video with valid FPS')
    writer=None
    if args.annotate:
        size=(int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        writer=cv2.VideoWriter(str(args.output/'review.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,size)
        if not writer.isOpened():capture.release();raise RuntimeError('Cannot create annotation video')
    gallery=IdentityGallery(args.threshold,args.margin);rows=[];timings=[];frame_index=0
    try:
        while True:
            ok,frame=capture.read()
            if not ok:break
            start=time.perf_counter();faces=app.get(frame);timings.append((time.perf_counter()-start)*1000)
            embeddings=[];valid=[]
            for face in faces:
                vector=np.asarray(face.embedding,dtype=np.float32)
                norm=np.linalg.norm(vector)
                if not np.isfinite(vector).all() or norm<1e-8:continue
                embeddings.append(vector/norm);valid.append(face)
            qualities=[float(f.det_score)>=.70 and min(f.bbox[2]-f.bbox[0],f.bbox[3]-f.bbox[1])>=40 for f in valid]
            matches=gallery.update(embeddings,qualities)
            items=[]
            for i,face in enumerate(valid):
                match=matches[i];identity=match['person']
                items.append({**match,'box':face.bbox.tolist(),'score':float(face.det_score)})
                if match['status']=='enrolled':
                    x0,y0,x1,y1=face.bbox.astype(int);h,w=frame.shape[:2]
                    crop=frame[max(0,y0):min(h,y1),max(0,x0):min(w,x1)]
                    if crop.size:cv2.imwrite(str(args.output/f'person-{identity:03}.jpg'),crop)
            rows.append({'frame':frame_index,'faces':items});frame_index+=1
            if frame_index%250==0:print(f'Processed {frame_index} frames; people={len(gallery.people)}',flush=True)
            if writer is not None:
                for item in items:
                    x0,y0,x1,y1=map(int,item['box']);color=(128,237,184) if item['person'] is not None else (60,190,255)
                    cv2.rectangle(frame,(x0,y0),(x1,y1),color,2)
                    cv2.putText(frame,(f"Person {item['person']}" if item['person'] is not None else "Pending"),(x0,max(24,y0-8)),cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
                writer.write(frame)
    finally:
        capture.release()
        if writer is not None:writer.release()
    report={'prototype_only':True,'pack':args.pack,'providers':['CPUExecutionProvider'],
            'models':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in models},
            'frames':frame_index,'fps':fps,'tracklets':len(gallery.people),'association':'person_multitemplate_delayed_enrollment','templates_per_person':[len(p) for p in gallery.people],'enroll_threshold':.40,'confirmations':5,'quality_min_score':.70,'quality_min_face_px':40,'threshold':args.threshold,'margin':args.margin,
            'inference_ms_median':float(np.median(timings)) if timings else None,
            'inference_ms_p95':float(np.percentile(timings,95)) if timings else None,
            'limitations':['No tracker; identity proposals need human review','No guarantee for profile, back-facing or occluded faces',
                           'Embeddings stay in memory; report stores boxes and proposed IDs only',
                           'Not a privacy-safe mask export; no production behavior changed'], 'detections':rows}
    (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='detections'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
