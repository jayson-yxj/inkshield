from pathlib import Path
import torch,json,hashlib
from safetensors.torch import load_file
import onnx
root=Path(__file__).resolve().parent
torch.set_num_threads(1)
rec={}
try:
 class InertModelCheckpoint:
  pass
 # Allow only inert stand-in for serialized Lightning callback identity;
 # continue weights_only deserialization, never import/execute third-party code.
 with torch.serialization.safe_globals([(InertModelCheckpoint,'pytorch_lightning.callbacks.model_checkpoint.ModelCheckpoint')]):
  old=torch.load(root/'adaface_ir50_ms1mv2.ckpt',map_location='cpu',weights_only=True)
 old_state={k[6:]:v for k,v in old['state_dict'].items() if k.startswith('model.')}
 new_state={k.removeprefix('model.net.'):v for k,v in load_file(root/'author-model.safetensors').items()}
 keys=set(old_state)&set(new_state)
 equal=[k for k in keys if torch.equal(old_state[k],new_state[k])]
 flipped=[]
 k='input_layer.0.weight'
 rec['old_new']={'original_keys':len(old_state),'new_keys':len(new_state),'common_keys':len(keys),'exact_equal_keys':len(equal),'first_conv_equal':torch.equal(old_state[k],new_state[k]),'first_conv_channel_reversed_equal':torch.equal(old_state[k][:,[2,1,0]],new_state[k]),'first_conv_max_abs_diff':float((old_state[k]-new_state[k]).abs().max()),'different_keys':[k for k in sorted(keys) if k not in equal][:20]}
except Exception as e:rec['old_new_error']=repr(e)
p=root.parent/'arcface-comparison/w600k_r50.onnx'
if p.exists():
 m=onnx.load(str(p),load_external_data=False)
 rec['arcface']={'input':str(m.graph.input[0]),'first_nodes':[{'op':n.op_type,'input':list(n.input),'output':list(n.output)} for n in list(m.graph.node)[:8]],'op_types':sorted({n.op_type for n in m.graph.node})}
(root/'weight-and-graph-inspection.json').write_text(json.dumps(rec,indent=2),encoding='utf8');print(json.dumps(rec,indent=2))
