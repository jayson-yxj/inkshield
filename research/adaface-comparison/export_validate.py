"""Export the official checkpoint without production environment dependencies."""
from pathlib import Path
import sys,json,hashlib,time,importlib.util
import numpy as np
import torch
import onnx
import onnxruntime as ort
from adaface_adapter import preprocess_bgr,AdaFaceCPU
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('official_net',root/'official/net.py')
net=importlib.util.module_from_spec(spec);spec.loader.exec_module(net)
torch.set_num_threads(2)
model=net.build_model('ir_50')
from safetensors.torch import load_file
checkpoint=load_file(root/'author-model.safetensors',device='cpu')
state={k.removeprefix('model.net.'):v for k,v in checkpoint.items()}
loaded=model.load_state_dict(state,strict=True);model.eval()
rng=np.random.default_rng(42);crop=rng.integers(0,256,(112,112,3),dtype=np.uint8)
x=preprocess_bgr(crop)
path=root/'adaface_ir50_ms1mv2.onnx'
with torch.no_grad():
 pt=model(torch.from_numpy(x))
 torch.onnx.export(model,torch.from_numpy(x),str(path),input_names=['bgr_input'],output_names=['embedding','norm'],opset_version=17,dynamic_axes={'bgr_input':{0:'batch'},'embedding':{0:'batch'},'norm':{0:'batch'}},dynamo=False)
onnx.checker.check_model(onnx.load(path))
adapter=AdaFaceCPU(path,threads=2)
start=time.perf_counter();emb,norm=adapter.infer(crop);elapsed=time.perf_counter()-start
# Official to_input is independent and imports GPU alignment; execute only its function.
source=(root/'official/inference.py').read_text();start_def=source.index('def to_input(');end_def=source.index("if __name__",start_def)
ns={'np':np,'torch':torch};exec(source[start_def:end_def],ns)
official_x=ns['to_input'](crop).numpy() # reference formula with same channel values; newer author model RGB
np.testing.assert_array_equal(x,official_x)
np.testing.assert_allclose(emb,pt[0].detach().numpy().reshape(-1),atol=2e-5,rtol=2e-4)
np.testing.assert_allclose(norm,pt[1].item(),atol=2e-4,rtol=2e-4)
sentinel=np.zeros((112,112,3),dtype=np.uint8);sentinel[:]=[0,127,255]
rec={'status':'validated','versions':{'torch':torch.__version__,'numpy':np.__version__,'onnx':onnx.__version__,'onnxruntime':ort.__version__},'state_keys':len(state),'parameters':sum(p.numel() for p in model.parameters()),'preprocessing_exact_equal_to_official':True,'BGR_0_127_255_tensor':preprocess_bgr(sentinel)[0,:,0,0].tolist(),'max_abs_embedding_error':float(np.max(np.abs(emb-pt[0].detach().numpy().reshape(-1)))),'pytorch_norm':pt[1].item(),'onnx_norm':norm,'unit_norm':float(np.linalg.norm(emb)),'one_cpu_inference_seconds':elapsed,'providers':adapter.session.get_providers(),'files':[]}
for p in [root/'author-model.safetensors',path,root/'adaface_adapter.py']:
 rec['files'].append({'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(root/'validation.json').write_text(json.dumps(rec,indent=2),encoding='utf8');print(json.dumps(rec,indent=2))
