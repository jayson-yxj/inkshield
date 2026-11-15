from pathlib import Path
import json
p=Path(__file__).parent
r=json.loads((p/'native-report.json').read_text(encoding='utf-8'))
checks=r.get('dom',{}).get('checks',[])
lines=['# Frozen effect track WebView2 acceptance','',f"Result: {'PASS' if r['passed'] else 'FAIL'}",f"HTML SHA-256: {r['hashes']['index.html']}",f"DOM checks: {sum(x['passed'] for x in checks)}/{len(checks)}",f"Browser errors: {r.get('browser_errors',[])}",f"Owned service: {r.get('service')}",f"Cleanup: {r.get('cleanup')}",f"All frozen sources unchanged: {all(r.get('sources_unchanged',{}).values())}",'','Scope: real Windows WebView2 dispatched DOM PointerEvents with capture shim; controlled immutable analysis masks/boxes; real backend FFmpeg encoding and decoded output frames. No OS mouse input or model quality claim. User port 50164 untouched. Production files not modified.','','First attempt used a 150-frame custom fixture for a 75-frame segment and correctly failed playback validation. Original failure retained in attempt1-fixture-mismatch.json. Fixed by adding controlled-custom-left (start 0, length 75), without production changes.','','## DOM checks','']
lines.extend(f"- {'PASS' if c['passed'] else 'FAIL'}: {c['name']}" for c in checks)
lines+=['','## Encoded artifacts','']
for a in r.get('assets',[]):lines.append(f"- {a['name']}: {a['frames']} frames; {a['streams']}; SHA-256 {a['sha256']}. Boundary center checks inside black [20,50) at frames 20/49 and outside at 19/50/79/110 passed.")
if r.get('error'):lines+=['','## Failure','',r['error']]
(p/'RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'passed':r['passed'],'checks':len(checks),'assets':len(r.get('assets',[])),'cleanup':r.get('cleanup')},ensure_ascii=False))
