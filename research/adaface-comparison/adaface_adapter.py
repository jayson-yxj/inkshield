"""Author CVLFace AdaFace IR50 MS1MV2 CPU adapter for aligned OpenCV crops.

This official newer checkpoint declares RGB (config.json, model.yaml). Convert
OpenCV BGR to RGB. Original 2022 AdaFace checkpoint instead requires BGR.
Alignment is the caller's responsibility. ONNX emits unit embedding + raw norm.
"""
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = ROOT / 'adaface_ir50_ms1mv2.onnx'


def preprocess_bgr(aligned_bgr):
    """Convert one uint8 [112,112,3] BGR crop to float32 [1,3,112,112]."""
    image = np.asarray(aligned_bgr)
    if image.shape != (112, 112, 3) or image.dtype != np.uint8:
        raise ValueError('AdaFace requires aligned 112x112x3 uint8 BGR; got %s %s' % (image.shape, image.dtype))
    # Match the author's float64 numpy arithmetic followed by torch.float().
    normalized = ((image[:, :, ::-1] / 255.0) - 0.5) / 0.5
    return np.ascontiguousarray(normalized.transpose(2, 0, 1)[None], dtype=np.float32)


class AdaFaceCPU:
    def __init__(self, model_path=DEFAULT_MODEL, threads=2):
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = int(threads)
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name

    def infer(self, aligned_bgr):
        """Return (unit 512-vector, raw embedding L2 norm/quality proxy)."""
        outputs = self.session.run(None, {self.input_name: preprocess_bgr(aligned_bgr)})
        embedding = np.asarray(outputs[0], dtype=np.float32).reshape(-1)
        norm = float(np.asarray(outputs[1]).reshape(-1)[0])
        if embedding.size != 512 or not np.isfinite(embedding).all() or not np.isfinite(norm):
            raise RuntimeError('Invalid AdaFace model output')
        return embedding, norm

    def get_feat(self, aligned_bgr):
        """Return unit embedding only, compatible with a crop embedding runner."""
        return self.infer(aligned_bgr)[0]
