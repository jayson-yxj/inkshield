"""Preserve last live checkpoints as partial evidence after bounded harness termination."""
import json
from pathlib import Path
out=Path(__file__).resolve().parent
report=json.loads((out/'ui-checkpoint.json').read_text(encoding='utf-8'))
report.update(passed=False,partial=True,limitation='OS harness stalled at window.evaluate_js after owned Win32 foreground activation. No OS click or UI preview request was executed. Final attempt also stalled after removal of window.focus. Application failure is not established by this harness block.',verified_scope='Fresh frozen page adopted CUDA ready device; ready text; complete6454frame import; long segment preview allowed and propagation150 blocked. Initial page opened after ready; warming UI not observed.',owned_jobs_collected=['pwsh-cf9f8e4ee86742ab','pwsh-61be727824514843','pwsh-7815e975097c4fa1','pwsh-229b8df441ac45cb','pwsh-e1b84c6b8eca4aaf','pwsh-49e27159aecc4e9a'])
(out/'ui-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':report['checks'],'partial':True,'passed':False,'last_js':report['last_js']},ensure_ascii=False,indent=2))
