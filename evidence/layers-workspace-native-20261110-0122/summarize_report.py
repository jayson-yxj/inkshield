from pathlib import Path
import json
p=Path(__file__).resolve().parent
r=json.loads((p/'native-report.json').read_text(encoding='utf-8'))
print('PASSED',r['passed'],'checks',len(r.get('dom',{}).get('checks',[])))
for o in r.get('dom',{}).get('observations',[]):
 if o.get('kind')=='automatic-to-final-custom': print('TAIL',o['cut'],'forced',o['forced_source_ended'],'frame',o['final']['frame'],'events',[(e['node'],e['type']) for e in o['events']])
 if 'distinct_visible_during' in o: print('SCRUB',json.dumps({k:v for k,v in o.items() if k in ['name','distinct_visible_during','renderTimeline_calls','events','max_preview_inflight_body','preview_aborted_during_held']}))
for x in r.get('pixel_checks',[]):print('VIDEO',x['asset'],'comparisons',len(x['checks']),'max MAE',max(c['mae'] for c in x['checks']))
print('JPEG checks',len(r.get('jpeg_checks',[])),'max',max((c['mae'] for c in r.get('jpeg_checks',[])),default=0))
print('sources',all(r.get('sources_unchanged',{}).values()),'cleanup',r.get('cleanup'))
