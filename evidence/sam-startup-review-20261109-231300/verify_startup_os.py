"""Real full-length source upload and real Windows OS point click; no fixtures/mocks."""
from pathlib import Path
import base64, ctypes, hashlib, json, time, traceback, urllib.request
from ctypes import wintypes
ctypes.windll.user32.SetProcessDPIAware()
import argparse
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--base',default='http://127.0.0.1:50164');p.add_argument('--require-warming',action='store_true');a=p.parse_args()
if not a.execute:p.error('Prepared only; requires freeze and OS slot authorization')
import webview
from PIL import ImageGrab
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
STATE={'url':a.base}
SOURCE=Path(r'C:\Users\36301\Desktop\5.mp4')
TITLE='Inkshield startup automatic-device OS review'
result={'state':STATE,'checks':[],'source_bytes':SOURCE.stat().st_size,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
window=webview.create_window(TITLE,STATE['url'],width=1420,height=780)
def run():
    def js(code):
        result['last_js']=code[:250]
        (OUT/'ui-checkpoint.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('JS '+code[:100],flush=True)
        value=window.evaluate_js(code)
        return value
    def wait(expr, timeout=180):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=js(expr)
            if value:return value
            time.sleep(.1)
        raise AssertionError('Timeout '+expr+' '+str(js("({sam:$('#samStatus').textContent,global:globalFrame,frames,importing})")))
    def check(name,expr):
        assert js(expr),name
        result['checks'].append(name)
        print('PASS '+name,flush=True)
    try:
        window.move(0,0)
        wait("typeof samCapabilities!=='undefined'&&samCapabilities?.available&&document.readyState==='complete'",60)
        with urllib.request.urlopen(STATE['url'],timeout=30) as response: result['served_index_sha256']=hashlib.sha256(response.read()).hexdigest()
        result['initial_warmup']=js("({state:samWarmup.state,text:$('#samWarmupStatus').textContent,blocked:samWarmupBlocked()})")
        result['warming_observed']=result['initial_warmup']['state'] in ('pending','warming')
        if a.require_warming:
            assert result['warming_observed'], 'OS page opened after warmup; warming UI not observed'
            check('Warming status visible', "samWarmupBlocked()&&$('#samWarmupStatus').textContent.includes('预热中')")
        wait("samWarmup.state==='ready'",600)
        ready_device=js('samWarmup.device')
        assert ready_device in ('cpu','cuda')
        result['ready_device']=ready_device
        check('Automatic ready device adopted',"settings.samDevice===samWarmup.device&&$('#samDevice').value===samWarmup.device&&!samWarmupBlocked()")
        check('Ready status visible',"$('#samWarmupStatus').textContent.includes('模型已就绪')")
        js("window.__errors=[];addEventListener('error',e=>__errors.push(e.message));addEventListener('unhandledrejection',e=>__errors.push(String(e.reason)));window.__requests=[];window.__responses=[];window.__realFetch=fetch;window.fetch=async function(url,options){const r={url:String(url),body:typeof options?.body==='string'?options.body:null};__requests.push(r);const response=await __realFetch.apply(this,arguments);r.http=response.status;if(String(url).includes('/api/sam/preview'))__responses.push({request:r,data:await response.clone().json()});return response}")
        # Full original 31MB upload via normal file-input change path. Chunk transfer
        # avoids passing a single oversized string to WebView2's evaluate bridge.
        js('window.__uploadChunks=[]')
        raw=SOURCE.read_bytes()
        for offset in range(0,len(raw),1024*1024):
            chunk=base64.b64encode(raw[offset:offset+1024*1024]).decode('ascii')
            js('__uploadChunks.push(Uint8Array.from(atob('+json.dumps(chunk)+'),c=>c.charCodeAt(0)))')
        js("(()=>{const dt=new DataTransfer();dt.items.add(new File(__uploadChunks,'5.mp4',{type:'video/mp4'}));$('#file').files=dt.files;$('#file').dispatchEvent(new Event('change',{bubbles:true}));delete window.__uploadChunks})()")
        wait('!!media&&!importing&&source.readyState>=2&&clipSelected')
        check('Original full 6454-frame range retained', 'media.frames===6454&&selectedSegment.start===0&&selectedSegment.end===6454&&frames===6454')
        js("$('#customMode').click()")
        wait("settings.mode==='custom'&&samDisplayed===JSON.stringify([selectedSegment.id,0,generation])&&!playbackCanvas.hidden&&!source.seeking")
        check('Long clip can preview but propagation disabled with clear 150 limit', "!samPreviewLimitError()&&$('#analyzeBtn').disabled&&$('#samModeNote').textContent.includes('150')")
        js('(()=>{playbackCanvas.scrollIntoView({block:"nearest"});return true})()')
        box=js("(()=>{const e=playbackCanvas,r=e.getBoundingClientRect(),s=Math.min(r.width/e.width,r.height/e.height),w=e.width*s,h=e.height*s;return {x:r.left+(r.width-w)/2+(646.5)/media.width*w,y:r.top+(r.height-h)/2+(218.5)/media.height*h,vw:innerWidth,vh:innerHeight}})()")
        u=ctypes.windll.user32
        u.FindWindowW.restype=wintypes.HWND
        u.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]
        u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        u.SetForegroundWindow.argtypes=[wintypes.HWND]
        hwnd=u.FindWindowW(None,TITLE)
        assert hwnd
        u.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
        u.GetForegroundWindow.restype=wintypes.HWND
        u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype=wintypes.DWORD
        u.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL]
        u.BringWindowToTop.argtypes=[wintypes.HWND]
        u.ShowWindow(hwnd,9)
        owner=wintypes.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        result['window_pid']=owner.value
        import os
        assert owner.value==os.getpid(), 'Window title belongs to another process'
        # Windows focus lock can reject SetForegroundWindow from the webview worker.
        # An actual ALT down/up and thread-input attachment permits owned activation.
        u.keybd_event(0x12,0,0,0);u.keybd_event(0x12,0,2,0)
        current=ctypes.windll.kernel32.GetCurrentThreadId()
        fg_thread=u.GetWindowThreadProcessId(u.GetForegroundWindow(),None)
        attached=bool(u.AttachThreadInput(current,fg_thread,True)) if current!=fg_thread else False
        try:
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
        finally:
            if attached:u.AttachThreadInput(current,fg_thread,False)
        time.sleep(.4)
        assert u.GetForegroundWindow()==hwnd, {'owned':hwnd,'foreground':u.GetForegroundWindow()}
        js("(()=>{window.__clicks=[];for(const kind of ['pointerdown','pointerup','click'])document.addEventListener(kind,e=>__clicks.push({kind,x:e.clientX,y:e.clientY,target:e.target.id}),true);return true})()")
        result['element_at_target']=js('(()=>{const e=document.elementFromPoint('+str(box['x'])+','+str(box['y'])+');return {id:e?.id,tag:e?.tagName}})()')
        rect=wintypes.RECT();assert u.GetClientRect(hwnd,ctypes.byref(rect))
        point=wintypes.POINT(round(box['x']*rect.right/box['vw']),round(box['y']*rect.bottom/box['vh']))
        assert u.ClientToScreen(hwnd,ctypes.byref(point))
        result['OS_click']={'geometry':box,'screen':[point.x,point.y],'hwnd':hwnd,'foreground':u.GetForegroundWindow(),'client':[rect.right,rect.bottom]}
        u.SetCursorPos(point.x,point.y);u.mouse_event(2,0,0,0,0);u.mouse_event(4,0,0,0,0)
        time.sleep(.3)
        result['click_events']=js('__clicks')
        ImageGrab.grab().save(OUT/'ui-click-diagnostic.png')
        wait('samPoints().length===1',10)
        wait("__responses.length===1&&!samClickRunning&&($('#samViewerStatus').textContent.includes('当前帧预览已计算')||$('#samViewerStatus').textContent.includes('当前帧未检测到目标区域'))",120)
        check('One positive original-coordinate point recorded', "samPoints().length===1&&samPoints()[0].label===1&&Math.abs(samPoints()[0].x-646)<=4&&Math.abs(samPoints()[0].y-218)<=4")
        check('Visible viewer status and 150 propagation explanation', "!$('#samViewerStatus').hidden&&($('#samViewerStatus').textContent.includes('当前帧预览已计算')||$('#samViewerStatus').textContent.includes('当前帧未检测到目标区域'))&&$('#samModeNote').textContent.includes('150')&&$('#analyzeBtn').disabled")
        check('Genuine full-range ready-device frame0 preview HTTP200 and no analysis', "__responses[0].request.http===200&&JSON.parse(__responses[0].request.body).end_frame===6454&&JSON.parse(__responses[0].request.body).frame===0&&JSON.parse(__responses[0].request.body).device===samWarmup.device&&!__requests.some(r=>r.url.includes('/api/sam/analyze'))&&!analysisReady")
        # Verify the drawn green point from actual canvas pixels at its center.
        check('Positive point marker drawn visibly on canvas', "(()=>{const p=samPoints()[0],d=playbackCanvas.getContext('2d').getImageData(Math.round(p.x/media.width*playbackCanvas.width),Math.round(p.y/media.height*playbackCanvas.height),1,1).data;return d[0]===170&&d[1]===255&&d[2]===85&&!playbackCanvas.hidden})()")
        check('No browser errors','__errors.length===0')
        result['actual_point']=js('samPoints()[0]')
        result['status']=js("$('#samViewerStatus').textContent")
        result['requests']=js('__requests')
        response=js('__responses[0].data')
        (OUT/'ui-preview-mask.png').write_bytes(base64.b64decode(response.pop('mask'),validate=True))
        result['preview']=response
        assert response['timing_ms']['model_load']==0
        assert response['timing_ms']['encoder']>0 and response['cache_hit'] is False
        result['scope']='OS click frame0 only; API script separately checks new frame; no propagation' 
        canvas=js('playbackCanvas.toDataURL()').split(',',1)[1]
        (OUT/'ui-canvas.png').write_bytes(base64.b64decode(canvas))
        ImageGrab.grab().save(OUT/'ui-os-screenshot.png')
        result['passed']=True
    except BaseException:
        result['passed']=False;result['error']=traceback.format_exc()
        print(result['error'],flush=True)
    finally:
        (OUT/'ui-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('UI_RESULT '+str(result['passed']),flush=True)
        window.destroy()  # Close only this test-owned window, never the service.
webview.start(run,gui='edgechromium',debug=False)
