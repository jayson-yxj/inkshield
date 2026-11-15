from pathlib import Path
import numpy as np
import json,hashlib
from adaface_adapter import preprocess_bgr
root=Path(__file__).resolve().parent
sentinel=np.full((112,112,3),[0,127,255],dtype=np.uint8)
x=preprocess_bgr(sentinel)
np.testing.assert_array_equal(x[0,:,0,0],np.array([1,-1/255,-1],dtype=np.float32))
rng=np.random.default_rng(42);bgr=rng.integers(0,256,(112,112,3),dtype=np.uint8)
# Same numpy arithmetic as official to_input(PIL_RGB) before torch.tensor(...).float().
rgb=bgr[:,:,::-1]
reference=np.asarray([(((rgb/255.)-0.5)/0.5).transpose(2,0,1)],dtype=np.float32)
np.testing.assert_array_equal(preprocess_bgr(bgr),reference)
for invalid in [np.zeros((112,112,3),np.float32),np.zeros((100,100,3),np.uint8)]:
 try:preprocess_bgr(invalid)
 except ValueError:pass
 else:raise AssertionError('invalid input accepted')
rec={'status':'preprocessing_verified_only','model_inference_validated':False,'preprocessing_exact_equal':True,'BGR_0_127_255_tensor':x[0,:,0,0].tolist(),'shape':list(x.shape),'dtype':str(x.dtype),'adapter_sha256':hashlib.sha256((root/'adaface_adapter.py').read_bytes()).hexdigest()}
(root/'preprocessing-validation.json').write_text(json.dumps(rec,indent=2),encoding='utf8');print(json.dumps(rec,indent=2))
