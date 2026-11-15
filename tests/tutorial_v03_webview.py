"""Owned tutorial v03 native WebView2 regression, using the existing 50164 service."""
from pathlib import Path
import argparse, base64, hashlib, json, time
import webview
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:50164/')
parser.add_argument('--output', type=Path, default=ROOT / 'evidence' / 'tutorial-v03')
parser.add_argument('--source', type=Path, default=ROOT / 'tutorial-preview.html')
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
source = args.source
before = hashlib.sha256(source.read_bytes()).hexdigest()
result = {'source_sha256_before': before, 'engine': 'edgechromium', 'url': args.url, 'checks': []}
window = webview.create_window('Tutorial v03 native acceptance', url=result['url'], width=1440, height=1000)
script = r'''(async()=>{
const checks=[],check=(name,ok,detail)=>{checks.push({name,ok:!!ok,detail});if(!ok)throw Error(name+' '+JSON.stringify(detail))},sleep=ms=>new Promise(r=>setTimeout(r,ms));
const d=document;d.querySelector('#tutorialOpen').click();await sleep(700);
const f=d.querySelector('#tutorialFrame'),w=f.contentWindow,q=w.document,ev=s=>w.eval(s);
check('real dialog open',d.querySelector('#tutorialDialog').open);
check('same-origin tutorial route',w.location.pathname==='/tutorial'&&w.location.origin===location.origin,w.location.href);
check('version and duration',q.title.includes('03')&&ev('DURATION')===96&&q.querySelector('#seek').max==='96');
check('eight chapters',q.querySelectorAll('.step').length===8);
ev('playing=false;draw()');
const events=[];w.addEventListener('error',e=>events.push(String(e.error||e.message)));w.addEventListener('unhandledrejection',e=>events.push(String(e.reason)));
for(let i=0;i<8;i++){q.querySelectorAll('.step')[i].click();check('chapter '+(i+1),ev('active')===i&&ev('clock')===i*12&&q.querySelectorAll('[aria-current="true"]').length===1);}
for(let t=0;t<=96;t+=.125)ev('clock='+t+';draw()');check('all 769 sampled frames render',events.length===0,events);
ev('clock=96;playing=false;draw()');check('end state',q.querySelector('#time').textContent==='01:36 / 01:36'&&q.querySelector('#finish').textContent.includes('结束'));
q.querySelector('#play').click();check('play at end restarts',ev('playing&&clock===0'));q.querySelector('#play').click();const paused=ev('clock');await sleep(180);check('pause holds clock',ev('clock')===paused);
q.querySelector('#seek').value=49.5;q.querySelector('#seek').dispatchEvent(new Event('input'));check('range input seeks',ev('clock===49.5&&active===4'));
q.querySelector('#replay').click();check('replay starts zero',ev('clock===0&&playing'));await sleep(240);check('native RAF advances',ev('clock>0&&clock<1'));q.querySelector('#play').click();
const motion=ev(`(()=>{let maxJump=0,maxBoundaryJump=0,maxVelocityMismatch=0;for(let t=.001;t<=96;t+=.001){const a=pointerAt(t-.001),b=pointerAt(t);maxJump=Math.max(maxJump,Math.hypot(a.x-b.x,a.y-b.y))}for(const k of motionKeys.slice(1,-1)){const a=pointerAt(k[0]-.0001),b=pointerAt(k[0]),c=pointerAt(k[0]+.0001);maxVelocityMismatch=Math.max(maxVelocityMismatch,Math.hypot(c.x-2*b.x+a.x,c.y-2*b.y+a.y)/.0001)}for(let t=12;t<96;t+=12){const a=pointerAt(t-.001),b=pointerAt(t+.001);maxBoundaryJump=Math.max(maxBoundaryJump,Math.hypot(a.x-b.x,a.y-b.y))}return{maxJump,maxBoundaryJump,maxVelocityMismatch,maxClickMiss:Math.max(...clickEvents.map(e=>{const p=pointerAt(e.t);return Math.hypot(p.x-e.x,p.y-e.y)}))}})()`);
check('continuous pointer at 1ms resolution',motion.maxJump<5,motion);check('continuous chapter boundaries',motion.maxBoundaryJump<5,motion);check('matching key velocities',motion.maxVelocityMismatch<1,motion);check('clicks meet cursor',motion.maxClickMiss<.01,motion);
check('failure preserves completed layer',ev('sceneState(50).failed&&sceneState(50).firstReady&&!sceneState(50).secondReady'));
check('retry completes pending layer',ev('sceneState(59).secondReady'));
check('batch first completion is 50 percent',ev('batchProgress(43)===.5'));
check('failed queue progress does not rewind',ev('batchProgress(47.99)<=batchProgress(48)&&batchProgress(50)===.75'));
check('retry has independent one-layer progress',ev('batchProgress(55)===0&&batchProgress(56.5)===.5&&batchProgress(58)===1'));
check('effect click targets layer three row',ev('actions.find(a=>a[0]===62)[2]===632'));
check('positive point is inside clothing target',ev('actions.find(a=>a[0]===25)[2]===330'));
check('close dialog before retry click',ev('clickEvents.some(e=>e.t===50&&e.x===853&&e.y===194)'));
check('empty layer blocks export until removed',ev('sceneState(85).empty&&!sceneState(85).exportReady&&!sceneState(87).empty&&sceneState(87).exportReady'));
q.querySelector('#steps').scrollIntoView({block:'end'});await sleep(80);const rect=q.querySelector('#steps').getBoundingClientRect();check('chapter controls reachable by iframe scrolling',rect.top>=0&&rect.bottom<=w.innerHeight+1,{rect:rect.toJSON(),height:w.innerHeight,scroll:w.scrollY});
ev('clock=46;playing=false;draw()');const screenshot=q.querySelector('canvas').toDataURL('image/png').split(',')[1];
d.querySelector('#tutorialClose').click();check('close unloads iframe and restores focus',!d.querySelector('#tutorialDialog').open&&!f.hasAttribute('src')&&d.activeElement.id==='tutorialOpen');d.querySelector('#tutorialOpen').click();await sleep(450);check('reopen creates fresh tutorial',f.contentWindow.eval('clock<2')&&f.contentDocument.querySelectorAll('.step').length===8);d.querySelector('#tutorialClose').click();
// Reduced-motion startup is tested in a fresh native iframe with matchMedia overridden before the source script.
const original=await (await fetch('/tutorial')).text();const reducedDoc=original.replace('<script>','<script>window.matchMedia=()=>({matches:true});<\/script><script>');const reducedFrame=d.createElement('iframe');reducedFrame.style.cssText='width:1000px;height:800px';d.body.append(reducedFrame);reducedFrame.srcdoc=reducedDoc;await sleep(250);check('reduced-motion starts paused',reducedFrame.contentWindow.eval('!playing&&clock===0'));reducedFrame.remove();
return {checks,motion,screenshot,browser:navigator.userAgent};
})().then(x=>window.__tutorialResult=x).catch(e=>window.__tutorialResult={error:String(e),stack:e.stack})'''
def run():
    try:
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if window.evaluate_js("!!document.querySelector('#tutorialOpen')"):
                break
            time.sleep(.1)
        window.evaluate_js('window.__tutorialResult=null;'+script)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            value=window.evaluate_js('window.__tutorialResult')
            if value is not None:
                result.update(value)
                break
            time.sleep(.2)
        else:
            result['error']='Native test timed out after 90 seconds'
        if 'screenshot' in result:
            (OUT/'batch-frame.png').write_bytes(base64.b64decode(result.pop('screenshot')))
    except Exception as exc:
        result['error']=str(exc)
    finally:
        result['source_sha256_after']=hashlib.sha256(source.read_bytes()).hexdigest()
        result['passed']=len([x for x in result['checks'] if x['ok']])
        result['source_unchanged']=result['source_sha256_before']==result['source_sha256_after']
        (OUT/'native-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        window.destroy()
webview.start(run,gui='edgechromium')
print(json.dumps(result,ensure_ascii=False))
raise SystemExit(1 if 'error' in result or not result['source_unchanged'] else 0)
