"""CPU SCRFD500m + MobileFaceNet for the authorized local research build.

Preprocessing/alignment derives from research/insightface_cpu.py. Official model
weights are noncommercial research assets; see models/FACE_SOURCE.md.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import cv2
import numpy as np
import onnxruntime as ort
from cpu_runtime import session_options
from scrfd import SCRFD

HASHES = {
    'det_500m.onnx': '5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a',
    'w600k_mbf.onnx': '9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f',
}
DST = np.array([[38.2946,51.6963],[73.5318,51.5014],[56.0252,71.7366],[41.5493,92.3655],[70.7299,92.2041]], dtype=np.float64)


def align_face(image, landmarks):
    src = np.asarray(landmarks, dtype=np.float64)
    if src.shape != (5, 2) or not np.isfinite(src).all():
        raise ValueError('Invalid five-point landmarks')
    sm, dm = src.mean(0), DST.mean(0)
    x, y = src-sm, DST-dm
    u, s, vt = np.linalg.svd(y.T @ x / len(x))
    sign = np.ones(2)
    if np.linalg.det(u)*np.linalg.det(vt) < 0:
        sign[-1] = -1
    variance = (x*x).sum()/len(x)
    if variance < 1e-9 or np.linalg.matrix_rank(x) < 2:
        raise ValueError('Degenerate five-point landmarks')
    linear = ((s*sign).sum()/variance) * (u @ np.diag(sign) @ vt)
    matrix = np.column_stack((linear, dm-linear @ sm))
    if not np.isfinite(matrix).all() or np.linalg.det(linear) <= 1e-12:
        raise ValueError('Invalid face alignment transform')
    return cv2.warpAffine(image, matrix, (112,112), borderValue=0.0)


class FaceDetector:
    def __init__(self, detection_path: Path, recognition_path: Path):
        for path, key in ((detection_path, 'det_500m.onnx'), (recognition_path, 'w600k_mbf.onnx')):
            if not path.is_file():
                raise RuntimeError(f'缺少本地模型：{path}')
            if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[key]:
                raise ValueError(f'Model hash mismatch: {path}')
        options = {'sess_options': session_options('human'), 'providers': ['CPUExecutionProvider']}
        self.session = ort.InferenceSession(str(detection_path), **options)
        self.detector = SCRFD(str(detection_path), session=self.session)
        self.detector.prepare(-1, det_thresh=.5, input_size=(640,640))
        if not self.detector.use_kps:
            raise ValueError('SCRFD model must provide five-point landmarks')
        self.recognition = ort.InferenceSession(str(recognition_path), **options)
        self.rec_input = self.recognition.get_inputs()[0].name

    def detect(self, frame, targets=('face',), threshold=.5):
        # Analysis is serialized by server.PROCESS_LOCK; threshold is per analysis.
        self.detector.det_thresh = threshold
        detections, landmarks = self.detector.detect(frame)
        if landmarks is None or len(landmarks) != len(detections):
            raise ValueError('Missing or misaligned five-point landmarks')
        height, width = frame.shape[:2]
        faces = []
        for row, points in zip(detections, landmarks):
            if row.shape != (5,) or not np.isfinite(row).all():
                raise ValueError('Invalid SCRFD detection')
            x0,y0,x1,y1 = np.clip(row[:4], [0,0,0,0], [width,height,width,height])
            if x1 <= x0 or y1 <= y0:
                raise ValueError('Invalid SCRFD face box')
            crop = align_face(frame, points)
            blob = cv2.dnn.blobFromImage(crop, 1/127.5, (112,112), (127.5,127.5,127.5), swapRB=True)
            embedding = np.asarray(self.recognition.run(None, {self.rec_input:blob})[0], dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(embedding))
            if embedding.shape != (512,) or not np.isfinite(embedding).all() or not np.isfinite(norm) or norm <= 1e-12:
                raise ValueError('Invalid embedding')
            faces.append(SimpleNamespace(bbox=np.array([x0,y0,x1,y1]), det_score=float(row[4]),
                                         normed_embedding=embedding/norm, thumbnail_crop=crop))
        return faces
