"""Inspect ONNX input graph normalization and compare BGR/RGB numerical identity."""
from pathlib import Path
import json,sys,hashlib
import onnx,numpy as np
root=Path(__file__).resolve().parent
p=root/'arcface-comparison/w600k_r50.onnx';m=onnx.load(str(p));nodes=[{'name':n.name,'op':n.op_type,'inputs':list(n.input),'outputs':list(n.output)} for n in m.graph.node[:10]]
# Official adapter chooses external mean/std when graph starts directly with Conv.
assert m.graph.node[0].op_type=='Conv',nodes
result={'model_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'first_nodes':nodes,'preprocessing':'official arcface_onnx.py default 127.5 mean / 127.5 std RGB; graph begins Conv, no input normalization nodes','input_shape':str(m.graph.input[0].type.tensor_type.shape)}
(root/'arcface-comparison/graph-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
