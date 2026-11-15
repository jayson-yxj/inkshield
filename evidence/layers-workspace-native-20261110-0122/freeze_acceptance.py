from pathlib import Path
import json,hashlib
out=Path(__file__).resolve().parent
root=out.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['index.html','layers_ui.js','workspace_ui.js','workspace_ui.css','server.py','preview_video.py','sam_service.py','mask_timeline.py','mask_layers.py','sam_engine.py','masking.py']
contract=json.loads((out/'integration.json').read_text(encoding='utf-8-sig'))
contract['state']='frozen'
contract['selectors'].update(layer_active_clear='#deleteMaskRegion',layer_region_start='.mask-handle.start',layer_region_end='.mask-handle.end')
contract['backend_sam_over_five_evidence']={'path':'BACKEND_LAYERS_REVIEW.md','sha256':sha(root/'BACKEND_LAYERS_REVIEW.md'),'test':'tests/test_sam_integration.py','test_sha256':sha(root/'tests/test_sam_integration.py'),'note':'Parent reported 51 tests/12.624 sec including seven analyses; this run uses controlled masks, not inference.'}
contract['pixel_expectations']={'protected':[],'export':[]}
required=['dom_suite.js','frozen_adapter.js','workspace_probe.js','workspace_cases.js','sam_cases.js','tail_cases.js','pixel_capture.js','reference_builder.py','pixel_oracle.py','controlled_fixtures.py','verify_mask_timeline_native.py']
contract['acceptance_hashes']={n:sha(out/n) for n in required}
(out/'integration.json').write_text(json.dumps(contract,indent=2,ensure_ascii=False),encoding='utf-8')
(out/'freeze.json').write_text(json.dumps({n:sha(root/n) for n in names},indent=2),encoding='utf-8')
print('Frozen source and acceptance hashes')
