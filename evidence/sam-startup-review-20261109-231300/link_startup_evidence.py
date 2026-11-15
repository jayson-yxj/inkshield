"""Link separately observed startup to the already completed API evidence; no requests."""
import hashlib,json
from pathlib import Path
out=Path(__file__).resolve().parent
api_path=out/'api-run'/'report.json';observer_path=out/'observer-run'/'report.json'
api=json.loads(api_path.read_text(encoding='utf-8'));observer=json.loads(observer_path.read_text(encoding='utf-8'))
assert observer['passed'] and observer['observed_warming_to_ready']
assert observer['base']==api['base'] and observer['ready']==api['ready']
assert observer['finished_at']<=api['started_at']
for name in ('desktop.py','sam_engine.py','sam_service.py'):assert observer['code_sha256'][name]==api['code_sha256'][name]
assert 'error' not in api
for key in ('first-real-preview','new-frame-preview'):
    row=api[key];assert row['status']==200 and row['timing_ms']['model_load']==0 and row['timing_ms']['encoder']>0 and row['cache_hit'] is False
assert api['long-propagation-rejection']['status']==422
api['api_checks_passed']=True
api['startup_evidence']={'path':str(observer_path),'sha256':hashlib.sha256(observer_path.read_bytes()).hexdigest()}
api['passed']=True
api['evidence_link_note']='API run began after ready; distinct prior observer recorded warming -> ready in same backend generation. No API inference was repeated to repair report bookkeeping.'
api_path.write_text(json.dumps(api,ensure_ascii=False,indent=2),encoding='utf-8')
print('Combined startup and API checks passed; original observed_warming_to_ready remains false for API-only run.')
