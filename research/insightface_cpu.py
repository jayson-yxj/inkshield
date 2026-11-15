"""Isolated Buffalo_sc CPU research adapter; not production SDK or redistributable weights.

SCRFD code loaded from saved official v0.7 source (onnx import unused and removed).
Recognition preprocessing follows saved arcface_onnx.py. Five-point alignment uses
least-squares similarity via NumPy SVD instead of adding scikit-image.
Only supports the two SHA256-pinned official Buffalo_sc models.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import cv2
import numpy as np
import onnxruntime as ort

BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'insightface-source'
HASHES = {
 'det_500m.onnx':'5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a',
 'w600k_mbf.onnx':'9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f',
}
DST=np.array([[38.2946,51.6963],[73.5318,51.5014],[56.0252,71.7366],[41.5493,92.3655],[70.7299,92.2041]],dtype=np.float64)

def align_face(image, landmarks):
    src=np.asarray(landmarks,dtype=np.float64)
    if src.shape!=(5,2) or not np.isfinite(src).all():
        raise ValueError('Invalid five-point landmarks')
    sm,dm=src.mean(0),DST.mean(0)
    x,y=src-sm,DST-dm
    covariance=y.T@x/len(x)
    u,s,vt=np.linalg.svd(covariance)
    sign=np.ones(2)
    if np.linalg.det(u)*np.linalg.det(vt)<0: sign[-1]=-1
    rotation=u@np.diag(sign)@vt
    variance=(x*x).sum()/len(x)
    if variance<1e-9: raise ValueError('Degenerate five-point landmarks')
    scale=(s*sign).sum()/variance
    linear=scale*rotation
    matrix=np.column_stack((linear,dm-linear@sm))
    return cv2.warpAffine(image,matrix,(112,112),borderValue=0.0)

class FaceAnalysis:
    def __init__(self,name='buffalo_sc',root=None,allowed_modules=None,providers=None,sess_options=None,**kwargs):
        if name!='buffalo_sc': raise ValueError('Research adapter supports only buffalo_sc')
        if providers not in (None,['CPUExecutionProvider']): raise ValueError('CPU-only trial')
        requested=Path(root).expanduser()/'models'/name if root else SOURCE/'models'/name
        self.model_dir=requested
        if not self.model_dir.is_dir():
            raise FileNotFoundError(f'Model folder unavailable: {requested}; download manually from official source')
        for filename,expected in HASHES.items():
            p=self.model_dir/filename
            if hashlib.sha256(p.read_bytes()).hexdigest()!=expected: raise ValueError(f'Model hash mismatch: {p}')
        code=(SOURCE/'scrfd.py').read_text(encoding='utf-8').replace('import onnx\n','')
        ns={'__name__':'isolated_official_scrfd'}
        exec(compile(code,str(SOURCE/'scrfd.py'),'exec'),ns)
        if sess_options is None:
            sess_options=ort.SessionOptions();sess_options.intra_op_num_threads=4
            sess_options.add_session_config_entry('session.intra_op.allow_spinning','0')
        options={'sess_options':sess_options,'providers':['CPUExecutionProvider']}
        detsession=ort.InferenceSession(str(self.model_dir/'det_500m.onnx'),**options)
        self.det_model=ns['SCRFD'](str(self.model_dir/'det_500m.onnx'),session=detsession)
        self.recognition=ort.InferenceSession(str(self.model_dir/'w600k_mbf.onnx'),**options)
        self.rec_input=self.recognition.get_inputs()[0].name
        self.models={'detection':self.det_model,'recognition':self.recognition}
        self.allowed_modules=allowed_modules or ['detection','recognition']
    def prepare(self,ctx_id=-1,det_thresh=.5,det_size=(640,640),**kwargs):
        if ctx_id>=0: raise ValueError('CPU-only trial requires ctx_id=-1')
        self.det_model.prepare(-1,det_thresh=det_thresh,input_size=det_size)
    def get(self,image,max_num=0,**kwargs):
        det,kps=self.det_model.detect(image,max_num=max_num)
        result=[]
        for i,row in enumerate(det):
            face=SimpleNamespace(bbox=row[:4].copy(),det_score=float(row[4]),kps=kps[i].copy(),embedding=None)
            if 'recognition' in self.allowed_modules:
                crop=align_face(image,face.kps)
                blob=cv2.dnn.blobFromImage(crop,1/127.5,(112,112),(127.5,127.5,127.5),swapRB=True)
                embedding=self.recognition.run(None,{self.rec_input:blob})[0].reshape(-1)
                if not np.isfinite(embedding).all(): raise ValueError('Invalid embedding')
                face.embedding=embedding
                face.normed_embedding=embedding/max(float(np.linalg.norm(embedding)),1e-12)
            result.append(face)
        return result
