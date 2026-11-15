"""Repeat standalone recognition timings on a deterministic shared face subset."""
import argparse,json,time
from pathlib import Path
import cv2,numpy as np,onnxruntime as ort
p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--models',type=Path,nargs='+',required=True);p.add_argument('--colors',nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert len(a.models)==len(a.colors)
crops=np.load(a.cache/'crops.npy',mmap_mode='r');indexes=np.linspace(0,len(crops)-1,200,dtype=int);results=[]
for model,color in zip(a.models,a.colors):
 o=ort.SessionOptions();o.intra_op_num_threads=4;o.inter_op_num_threads=1;o.add_session_config_entry('session.intra_op.allow_spinning','0');s=ort.InferenceSession(str(model),sess_options=o,providers=['CPUExecutionProvider']);name=s.get_inputs()[0].name
 def run(i):
  b=cv2.dnn.blobFromImage(crops[i],1/127.5,(112,112),(127.5,)*3,swapRB=color=='rgb');return s.run(None,{name:b})
 for i in indexes[:5]:run(i)
 times=[]
 for i in indexes:
  t=time.perf_counter();run(i);times.append((time.perf_counter()-t)*1000)
 row={'model':str(model),'color':color,'faces':200,'threads':4,'median_ms':float(np.median(times)),'p95_ms':float(np.percentile(times,95))};results.append(row);print(row,flush=True)
 del s
(a.output).write_text(json.dumps({'scope':'200 deterministic evenly-spaced crops; sequential batch1 CPU recognition+preprocessing, 5 warmups; no detection or encode','results':results},indent=2))
