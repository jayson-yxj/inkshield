"""HTTP contract fixture, not SAM inference. Logs actual frontend requests."""
import time, copy
from fastapi.responses import JSONResponse

def install(api):
    state={'requests':[], 'jobs':{}, 'fail_at':None, 'overlap':False}
    @api.app.middleware('http')
    async def controlled(request, call_next):
        path=request.url.path
        if path=='/__fixture/reset' and request.method=='POST':
            cfg=await request.json()
            state.update(requests=[],jobs={},fail_at=cfg.get('fail_at'),overlap=False)
            return JSONResponse({'ok':True})
        if path=='/__fixture/state':
            return JSONResponse(state)
        if path=='/api/sam/capabilities':
            return JSONResponse({'available':True,'max_frames':150,'max_width':1920,'max_height':1080,'default_device':'cpu','devices':[{'id':'cpu','available':True},{'id':'cuda','available':True,'label':'Controlled CUDA contract only'}]})
        if path=='/api/sam/preview':
            # Transparent PNG; keeps point previews deterministic without model calls.
            import base64,io
            from PIL import Image
            stream=io.BytesIO();Image.new('RGBA',(320,240)).save(stream,format='PNG')
            return JSONResponse({'mask':'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode(),'seconds':0,'empty':True})
        if path=='/api/sam/analyze' and request.method=='POST':
            body=await request.json();n=len(state['requests'])+1
            if any(not j['terminal'] for j in state['jobs'].values()):state['overlap']=True
            job='batch-controlled-'+str(n)
            state['requests'].append({'number':n,'body':body,'at':time.monotonic(),'job_id':job})
            state['jobs'][job]={'polls':0,'terminal':False,'fail':n==state['fail_at']}
            api.ANALYSES[job]=api.ANALYSES['controlled-custom-a' if n%2 else 'controlled-custom-b']
            return JSONResponse({'job_id':job})
        if path.startswith('/api/status/batch-controlled-'):
            job=path.rsplit('/',1)[-1];item=state['jobs'][job];item['polls']+=1
            if item['polls']<3:
                return JSONResponse({'state':'loading' if item['polls']==1 else 'analyzing','progress':item['polls']*30,'message':'Controlled propagation'})
            item['terminal']=True;item['terminal_at']=time.monotonic()
            if item['fail']:return JSONResponse({'state':'error','error':'Controlled second-layer failure'})
            result={'state':'ready','kind':'analyze','frames':150,'fps':25,'width':320,'height':240,'start_frame':0,'end_frame':150,'progress':100,'mode':'custom'}
            api.JOBS[job]=result
            return JSONResponse(result)
        return await call_next(request)
