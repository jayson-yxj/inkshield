"""Isolated model comparison on identical cached aligned face crops."""
import argparse,json,time,hashlib
from pathlib import Path
import cv2,numpy as np,onnxruntime as ort
from insightface_cpu import FaceAnalysis,align_face
from identity_gallery import IdentityGallery

def options():
 o=ort.SessionOptions();o.intra_op_num_threads=4;o.inter_op_num_threads=1;o.add_session_config_entry('session.intra_op.allow_spinning','0');return o

def cache(video,out):
 if not video.is_file():raise FileNotFoundError(video)
 baseline=json.loads(Path('runtime/insightface-desktop5-v2/report.json').read_text(encoding='utf-8'))
 out.mkdir(exist_ok=False,parents=True)
 total=sum(len(r['faces']) for r in baseline['detections'])
 crops=np.lib.format.open_memmap(out/'crops.npy',mode='w+',dtype=np.uint8,shape=(total,112,112,3))
 app=FaceAnalysis(root='research/insightface-models',allowed_modules=['detection'],sess_options=options());app.prepare()
 cap=cv2.VideoCapture(str(video));rows=[];offset=0;idx=0;timings=[]
 try:
  while True:
   ok,frame=cap.read()
   if not ok:break
   t=time.perf_counter();faces=app.get(frame);timings.append((time.perf_counter()-t)*1000)
   expected=baseline['detections'][idx]['faces'];assert len(faces)==len(expected),(idx,len(faces),len(expected))
   items=[]
   for f,e in zip(faces,expected):
    assert np.allclose(f.bbox,e['box'],atol=1e-5,rtol=0),(idx,f.bbox,e['box'])
    crops[offset]=align_face(frame,f.kps)
    items.append({'crop':offset,'box':f.bbox.tolist(),'score':f.det_score});offset+=1
   rows.append({'frame':idx,'faces':items});idx+=1
   if idx%500==0:print('CACHE',idx,offset,flush=True)
 finally:cap.release()
 assert idx==baseline['frames'] and offset==total
 crops.flush()
 (out/'cache.json').write_text(json.dumps({'video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'frames':idx,'fps':baseline['fps'],'crops':total,'alignment':'insightface five-point 112x112 BGR uint8','detection_boxes_match_v2':True,'detection_ms_median':float(np.median(timings)),'rows':rows}),encoding='utf-8')
 print('CACHE READY',idx,total,flush=True)

def evaluate(cachepath,model,output,label,color='rgb'):
 meta=json.loads((cachepath/'cache.json').read_text());crops=np.load(cachepath/'crops.npy',mmap_mode='r')
 output.mkdir(exist_ok=False,parents=True)
 session=ort.InferenceSession(str(model),sess_options=options(),providers=['CPUExecutionProvider']);inp=session.get_inputs()[0]
 print(label,inp.name,inp.shape,session.get_outputs()[0].shape,flush=True)
 times=[];vectors=[]
 # Sequential, batch-one CPU inference. Warmup excluded.
 def blob(crop):return cv2.dnn.blobFromImage(crop,1/127.5,(112,112),(127.5,127.5,127.5),swapRB=color=='rgb')
 for _ in range(5):session.run(None,{inp.name:blob(crops[0])})
 for i,crop in enumerate(crops):
  t=time.perf_counter();v=session.run(None,{inp.name:blob(crop)})[0].reshape(-1);times.append((time.perf_counter()-t)*1000)
  assert np.isfinite(v).all() and np.linalg.norm(v)>1e-8
  vectors.append(v/np.linalg.norm(v))
  if (i+1)%1000==0:print(label,i+1,'faces',flush=True)
 vectors=np.asarray(vectors,dtype=np.float32);np.save(output/'embeddings.npy',vectors)
 gallery=IdentityGallery();rows=[]
 for row in meta['rows']:
  faces=row['faces'];q=[f['score']>=.70 and min(f['box'][2]-f['box'][0],f['box'][3]-f['box'][1])>=40 for f in faces]
  matches=gallery.update([vectors[f['crop']] for f in faces],q)
  rows.append({'frame':row['frame'],'faces':[{**f,**m} for f,m in zip(faces,matches)]})
 report={'prototype_only':True,'pack':label,'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'frames':meta['frames'],'fps':meta['fps'],'tracklets':len(gallery.people),'templates_per_person':[len(p) for p in gallery.people],'threshold':.50,'margin':.10,'association':'same frozen v2 gallery defaults; thresholds uncalibrated per model','recognition_ms_median':float(np.median(times)),'recognition_ms_p95':float(np.percentile(times,95)),'recognition_total_seconds':sum(times)/1000,'timing_scope':'single aligned face preprocessing plus recognition only; excludes detection/decode/association/encode','detections':rows}
 (output/'report.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='detections'},indent=2),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['cache','evaluate']);p.add_argument('--video',type=Path);p.add_argument('--cache',type=Path,default=Path('runtime/recognition-comparison-cache'));p.add_argument('--model',type=Path);p.add_argument('--output',type=Path);p.add_argument('--label');p.add_argument('--color',choices=['rgb','bgr'],default='rgb');a=p.parse_args()
 if a.mode=='cache':cache(a.video,a.cache)
 else:evaluate(a.cache,a.model,a.output,a.label,a.color)
