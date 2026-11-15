from pathlib import Path
import json, importlib.util
OUT=Path(__file__).resolve().parent
for p in OUT.glob('*.py'):
    compile(p.read_text(encoding='utf-8'),str(p),'exec')
spec=importlib.util.spec_from_file_location('fixtures',OUT/'controlled_fixtures.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Fake:
    ANALYSES={};JOBS={}
    class Analysis:
        def __init__(self,**kw):self.__dict__.update(kw)
f=Fake();m.install(f,OUT/'source-audio.mp4')
assert len(f.ANALYSES)==15
for suffix in ['', '-head','-tail','-short-head','-short-tail']:
    trio=[f.ANALYSES['controlled-'+k+suffix] for k in m.RECTS]
    assert len({(a.input_path,a.start_frame,len(a.boxes),a.fps,a.width,a.height) for a in trio})==1
    assert all(not a.custom_masks[0].flags.writeable for a in trio[1:])
a=f.ANALYSES['controlled-custom-a'].custom_masks[0];b=f.ANALYSES['controlled-custom-b'].custom_masks[0]
assert (a & b).sum()>0 and (a & ~b).sum()>0 and (b & ~a).sum()>0
result={'python_syntax':'passed','fixture_install':'15 analyses; five aligned triples','immutable_masks':True,'custom_exclusive_and_overlap_rois':True,'native_acceptance':'NOT EXECUTED','server_started':False,'port_50164_touched':False}
(OUT/'preparation-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
