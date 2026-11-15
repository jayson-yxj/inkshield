"""Standalone WebView2 smoke test; uses no production server or media service."""
from pathlib import Path
import json
import webview

ROOT = Path(__file__).resolve().parents[1]
html = '''<!doctype html><html><head><style>
*{box-sizing:border-box}body{margin:0;background:#111;color:#eee}.workspace{width:1100px;height:700px;display:grid;grid-template-areas:"media mediaSplit stage inspectorSplit inspector" "rowSplit rowSplit rowSplit rowSplit rowSplit" "timeline timeline timeline timeline timeline"}.media-panel{grid-area:media}.controls{grid-area:inspector}.timeline{grid-area:timeline}.stage{grid-area:stage;display:flex;flex-direction:column;min-width:0;min-height:0}.viewer{position:relative;flex:1;min-height:0;overflow:hidden}.stage-bar{height:30px}#mediaResize{grid-area:mediaSplit}#inspectorResize{grid-area:inspectorSplit}#timelineResize{grid-area:rowSplit}[hidden]{display:none!important}
</style><style>''' + (ROOT / 'workspace_ui.css').read_text(encoding='utf-8') + '''</style></head><body><div id="editorWorkspace" class="workspace"><aside class="media-panel">Media</aside><aside class="controls"><button id="customMode" aria-pressed="true">Custom</button></aside><section class="timeline">Timeline</section><div class="stage"><div class="stage-bar">Preview</div><div id="viewer" class="viewer"><video id="source" hidden></video><img id="preview" hidden><video id="protectedPlayback" hidden></video><canvas id="playbackCanvas" width="1280" height="720"></canvas></div></div><div id="mediaResize"></div><div id="inspectorResize"></div><div id="timelineResize"></div></div><script>''' + (ROOT / 'workspace_ui.js').read_text(encoding='utf-8') + '''</script></body></html>'''
script = r'''(async()=>{
 const checks=[],check=(name,ok)=>{checks.push({name,ok:!!ok});if(!ok)throw Error(name)},$=s=>document.querySelector(s),v=$('#viewer'),w=$('#editorWorkspace');
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let clicks=0,settles=0;v.addEventListener('click',()=>clicks++);w.addEventListener('workspace:layoutsettled',()=>settles++);
 check('shared layers', ['source','preview','playbackCanvas','protectedPlayback'].every(id=>document.getElementById(id).parentElement.id==='previewTransform'));
 const r=v.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;
 v.dispatchEvent(new WheelEvent('wheel',{deltaY:-400,clientX:x,clientY:y,bubbles:true,cancelable:true}));
 check('wheel zoom',inkshieldWorkspaceUI.getPreviewState().zoom>1);
 const before=inkshieldWorkspaceUI.getPreviewState().zoom;
 document.body.dispatchEvent(new WheelEvent('wheel',{deltaY:-400,bubbles:true}));check('wheel region isolation',inkshieldWorkspaceUI.getPreviewState().zoom===before);
 v.dispatchEvent(new MouseEvent('click',{clientX:x,clientY:y,bubbles:true}));check('custom left click retained',clicks===1);
 // Synthetic pointer capture is unavailable: provide only the native capture hooks
 // so the real registered event handlers can be exercised with synthetic pointers.
 v.setPointerCapture=()=>{};v.hasPointerCapture=()=>false;
 v.dispatchEvent(new PointerEvent('pointerdown',{button:1,pointerId:23,clientX:x,clientY:y,bubbles:true,cancelable:true}));
 v.dispatchEvent(new PointerEvent('pointermove',{pointerId:23,clientX:x+20,clientY:y+10,bubbles:true}));
 v.dispatchEvent(new PointerEvent('pointerup',{pointerId:23,bubbles:true}));
 v.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));check('pan trailing click suppressed',clicks===1);check('pan changed',inkshieldWorkspaceUI.getPreviewState().x>0);
 v.dispatchEvent(new PointerEvent('pointerdown',{button:0,pointerId:24,bubbles:true}));v.dispatchEvent(new MouseEvent('click',{bubbles:true}));check('next custom click retained',clicks===2);
 $('#previewZoomReset').click();check('reset',inkshieldWorkspaceUI.getPreviewState().zoom===1&&inkshieldWorkspaceUI.getPreviewState().x===0);
 const sizes=['.media-panel','.controls','.timeline'].map(s=>{const r=$(s).getBoundingClientRect();return[r.width,r.height]});
 for(const [i,id,sel] of [[0,'toggleMediaPanel','.media-panel'],[1,'toggleInspectorPanel','.controls'],[2,'toggleTimelinePanel','.timeline']]){
  const b=$('#'+id),p=$(sel);b.click();await sleep(340);check(id+' collapsed aria',b.getAttribute('aria-expanded')==='false'&&p.inert);check(id+' collapsed track '+JSON.stringify({rect:p.getBoundingClientRect().toJSON(),tracks:getComputedStyle(w).gridTemplateColumns,win:innerWidth}),i===2?p.getBoundingClientRect().height<1:p.getBoundingClientRect().width<1);b.click();await sleep(340);check(id+' restored',Math.abs((i===2?p.getBoundingClientRect().height:p.getBoundingClientRect().width)-sizes[i][i===2?1:0])<1);
 }
 check('one settled event per toggle',settles===6);return {checks,passed:checks.length};
})()'''
window = webview.create_window('Workspace UI isolated test', html=html, width=1200, height=850, hidden=False)
result = {}
def run():
    try:
        import time
        window.evaluate_js('window.__testResult=null;' + script + '.then(r=>window.__testResult=r).catch(e=>window.__testResult={error:String(e)})')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            value = window.evaluate_js('window.__testResult')
            if value is not None:
                result.update(value)
                break
            time.sleep(0.1)
        else:
            result['error'] = 'WebView smoke test timed out'
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        window.destroy()
webview.start(run, gui='edgechromium')
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(1 if 'error' in result else 0)
