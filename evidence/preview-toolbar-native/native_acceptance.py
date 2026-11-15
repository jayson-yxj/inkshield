from pathlib import Path
import sys,os,json,hashlib,time,subprocess,urllib.request,base64,traceback,threading
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
FILES=['index.html','layers_ui.js','workspace_ui.css','workspace_ui.js','server.py','mask_layers.py','mask_timeline.py','sam_service.py','preview_video.py','sam_engine.py']
if '--prepare' in sys.argv:
 print(json.dumps({'state':'prepared_waiting_owner_freeze','server_started':False,'requires':['explicit --execute','contract.json state=frozen','freeze.json','final suite.js']}));sys.exit()
contract=json.loads((OUT/'contract.json').read_text(encoding='utf-8'))
assert contract['state']=='frozen','Owner freeze required before starting service'
assert '--execute' in sys.argv or '--server' in sys.argv,'Use --execute only after owner freeze'
if '--server' in sys.argv:
 os.environ['INKSHIELD_DATA_DIR']=str(OUT/'isolated-data')
 import server,sam_service,socket,uvicorn
 sam_service.WARMUP_STATE.update(state='ready',device='cpu',error=None)
 sys.path.insert(0,str(OUT))
 from controlled_fixtures import install
 install(server,OUT/'source-audio.mp4')
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];assert port!=50164
 (OUT/'service.json').write_text(json.dumps({'pid':os.getpid(),'url':f'http://127.0.0.1:{port}/'}))
 uvicorn.Server(uvicorn.Config(server.app,log_level='warning')).run(sockets=[sock]);sys.exit()
frozen=json.loads((OUT/'freeze.json').read_text(encoding='utf-8-sig'))
assert all(sha(ROOT/f)==h for f,h in frozen.items()),'Freeze differs'
import shutil
shutil.copyfile(ROOT/'evidence/layers-workspace-native-20261110-0122/source-audio.mp4',OUT/'source-audio.mp4')
os.environ['PYTHONPATH']=os.pathsep.join(sys.path)
os.environ['PYTHONIOENCODING']='utf-8'
log=(OUT/'server.log').open('w');proc=subprocess.Popen([getattr(sys,'_base_executable',sys.executable),__file__,'--server'],cwd=ROOT,stdout=log,stderr=log)
report={'hashes':frozen,'suite_sha256':sha(OUT/('slider_probe.js' if '--slider-probe' in sys.argv else 'suite.js')),'harness_sha256':sha(Path(__file__)), 'input_method':'Real WebView2 with synthetic DOM click/input events; immutable controlled analysis fixtures; no inference','passed':False}
try:
 for _ in range(350):
  assert proc.poll() is None,'Server exited'
  try:
   state=json.loads((OUT/'service.json').read_text());assert state['pid']==proc.pid
   with urllib.request.urlopen(state['url'],timeout=1) as r:assert hashlib.sha256(r.read()).hexdigest()==frozen['index.html']
   break
  except Exception:time.sleep(.1)
 else:raise Exception('Service timeout')
 report['service']=state
 import webview
 window=webview.create_window('Split and mode theme native acceptance',state['url'],width=1460,height=920)
 def run():
  def js(s):return window.evaluate_js(s)
  def wait(s,seconds=60):
   until=time.monotonic()+seconds
   while time.monotonic()<until:
    if js(s):return
    time.sleep(.08)
   raise Exception('Timeout '+s)
  def capture(name):
   from System import Action
   from System.IO import FileStream,FileMode,FileAccess
   from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
   native=window.native; box={};done=threading.Event()
   def begin():
    try:
     stream=FileStream(str(OUT/(name+'.png')),FileMode.Create,FileAccess.Write)
     task=native.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)
     box.update(task=task,stream=stream)
    except Exception as e:box['error']=str(e)
    done.set()
   native.Invoke(Action(begin));assert done.wait(10)
   if 'error' in box:raise Exception(box['error'])
   box['task'].Wait();box['stream'].Dispose()
  try:
   wait("typeof samCapabilities!=='undefined'&&!!samCapabilities&&document.readyState==='complete'")
   report['user_agent']=js('navigator.userAgent')
   js("window.__errors=[];window.addEventListener('error',e=>__errors.push(e.message));window.addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)))")
   data=base64.b64encode((OUT/'source-audio.mp4').read_bytes()).decode()
   js("(()=>{const dt=new DataTransfer();dt.items.add(new File([Uint8Array.from(atob("+json.dumps(data)+"),c=>c.charCodeAt(0))],'controlled-6s.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}))})()")
   wait('!!media&&!importing&&source.readyState>=2&&clipSelected')
   js((OUT/('slider_probe.js' if '--slider-probe' in sys.argv else 'suite.js')).read_text(encoding='utf-8'))
   if '--media-probe' in sys.argv:
    report['diagnostic_only']=True;report['probe_sha256']=sha(OUT/'media_probe.js');js((OUT/'media_probe.js').read_text(encoding='utf-8'))
   js("runSuite().catch(e=>{__suite.error=String(e.stack||e);__suite.state='failed'})")
   wait("['done','failed'].includes(__suite.state)",180)
   report['dom']=js('__suite');report['browser_errors']=js('__errors')
   capture('actual-app-custom')
   js("$('#modeToggle').click()");time.sleep(.7);capture('actual-app-automatic')
   from System import Action
   box={}
   def emulate():box['task']=window.native.webview.CoreWebView2.CallDevToolsProtocolMethodAsync('Emulation.setEmulatedMedia',json.dumps({'features':[{'name':'prefers-reduced-motion','value':'reduce'}]}))
   window.native.Invoke(Action(emulate));box['task'].Wait();time.sleep(.2)
   report['reduced_motion']=js("({matches:matchMedia('(prefers-reduced-motion: reduce)').matches,icon:getComputedStyle(document.querySelector('.mode-switch-icon')).transitionDuration,viewer:getComputedStyle($('#viewer')).transitionDuration,ring:getComputedStyle($('#viewer'),'::after').transitionDuration})")
   assert report['reduced_motion']=={'matches':True,'icon':'0s','viewer':'0s','ring':'0s'},report['reduced_motion']
   assert report['dom']['state']=='done',report['dom'].get('error')
   report['source_hashes_after']={f:sha(ROOT/f) for f in frozen}
   assert report['source_hashes_after']==frozen,'Source changed during acceptance'
   assert not report['browser_errors'],report['browser_errors']
   report['passed']=True
  except Exception:report['error']=traceback.format_exc()
  finally:
   (OUT/'native-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');window.destroy()
 webview.start(run,gui='edgechromium',debug=False)
finally:
 proc.terminate();proc.wait(timeout=15);log.close()
print(json.dumps({'passed':report['passed'],'error':report.get('error'),'report':str(OUT/'native-report.json')},ensure_ascii=False))
sys.exit(0 if report['passed'] else 1)
