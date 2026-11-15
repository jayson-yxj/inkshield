"""Isolated local SAM2.1 experiment; never imports or changes the released editor."""
from __future__ import annotations
import json, math, os, re, shutil, threading, time, uuid
from pathlib import Path
import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'runtime';DATA.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='隐映 SAM2.1 点选试验')
SESSIONS={};JOBS={};LOCK=threading.RLock();SLOT=threading.Lock();ENGINE=None
STYLES=('mosaic','blur','black')

def storage_check():
    total=sum(p.stat().st_size for p in DATA.rglob('*') if p.is_file())
    if total>3*1024**3:raise HTTPException(409,'试验缓存已达3GB，请停止服务并手动整理runtime后再试')

def read_jpeg(path):
    image=cv2.imdecode(np.frombuffer(Path(path).read_bytes(),np.uint8),cv2.IMREAD_COLOR)
    if image is None:raise RuntimeError('无法读取缓存帧')
    return image

class Point(BaseModel):
    x: float
    y: float
    label: int = Field(ge=0,le=1)
class SegmentOptions(BaseModel):
    prompts: dict[str,list[Point]]
class ExportOptions(BaseModel):
    style: str='mosaic'
    strength: int=Field(default=68,ge=20,le=100)
    padding: int=Field(default=6,ge=0,le=40)

def session(sid):
    with LOCK:s=SESSIONS.get(sid)
    if s is None:raise HTTPException(404,'视频不存在；此独立试验重启后需重新导入')
    return s

def frame_path(s,frame):
    if not 0<=frame<s['frames']:raise HTTPException(422,'帧超出范围')
    return s['folder']/'frames'/f'{frame:05d}.jpg'

def masks_ready(s):
    if s.get('masks') is None:raise HTTPException(409,'请先完成目标传播')

def render(frame,mask,style,strength,padding):
    if style not in STYLES:raise ValueError('未知样式')
    if mask.shape!=frame.shape[:2]:raise ValueError('掩码尺寸与原视频不一致')
    mask=(mask>0).astype(np.uint8)
    if padding:mask=cv2.dilate(mask,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(padding*2+1,padding*2+1)))
    if not mask.any():return frame.copy()
    ys,xs=np.nonzero(mask);x0,x1=max(0,int(xs.min())-2),min(frame.shape[1],int(xs.max())+3);y0,y1=max(0,int(ys.min())-2),min(frame.shape[0],int(ys.max())+3)
    crop=frame[y0:y1,x0:x1];h,w=crop.shape[:2]
    if style=='black':effect=np.zeros_like(crop)
    elif style=='blur':effect=cv2.GaussianBlur(crop,(0,0),max(3,min(h,w)*(.08+strength*.003)),borderType=cv2.BORDER_REPLICATE)
    else:
        blocks=max(4,int(24-strength*.18));sw=max(1,min(w,blocks));sh=max(1,min(h,round(sw*h/max(1,w))))
        effect=cv2.resize(cv2.resize(crop,(sw,sh),interpolation=cv2.INTER_AREA),(w,h),interpolation=cv2.INTER_NEAREST)
    # Privacy core remains opaque. Feather is intentionally not added in this first prototype.
    result=frame.copy();roi=result[y0:y1,x0:x1];roi[mask[y0:y1,x0:x1]>0]=effect[mask[y0:y1,x0:x1]>0]
    return result

@app.get('/')
def index():return FileResponse(ROOT/'index.html')
@app.get('/api/health')
def health():return {'ok':True,'model':'SAM2.1 tiny','device':'cpu','max_frames':150,'max_pixels':1280*720,'loaded':ENGINE is not None}

@app.post('/api/import')
async def import_video(video:UploadFile=File(...)):
    if not SLOT.acquire(blocking=False):raise HTTPException(409,'已有任务正在运行')
    folder=DATA/uuid.uuid4().hex
    try:
        storage_check()
        if sum(p.is_dir() and re.fullmatch(r'[0-9a-f]{32}',p.name) is not None for p in DATA.iterdir())>=5:raise HTTPException(409,'试验缓存最多5段视频，请停止服务后手动整理runtime，重启不会重置此限制')
        folder.mkdir();source=folder/'source.mp4';size=0
        with source.open('wb') as f:
            while chunk:=await video.read(1024*1024):
                size+=len(chunk)
                if size>256*1024*1024:raise HTTPException(413,'试验输入上限256MB')
                f.write(chunk)
        cap=cv2.VideoCapture(str(source))
        if not cap.isOpened():
            cap.release();raise HTTPException(422,'无法解码视频')
        fps=float(cap.get(cv2.CAP_PROP_FPS));width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not math.isfinite(fps) or fps<=0:
            cap.release();raise HTTPException(422,'无效帧率')
        if width<=0 or height<=0 or width>1280 or height>720:
            cap.release();raise HTTPException(422,'本次CPU试验支持最高1280×720，请使用小片段')
        if width%2 or height%2:
            cap.release();raise HTTPException(422,'试验导出要求宽高均为偶数')
        expected=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames=folder/'frames';frames.mkdir();count=0
        try:
            while count<150:
                ok,frame=cap.read()
                if not ok:break
                if frame.shape[:2]!=(height,width):raise HTTPException(422,'视频尺寸发生变化')
                encoded,buffer=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,96])
                if not encoded:raise RuntimeError('帧保存失败')
                (frames/f'{count:05d}.jpg').write_bytes(buffer.tobytes())
                count+=1
            truncated=bool(cap.grab())
            if count<150 and expected>count:raise HTTPException(422,f'视频解码提前中断：{count}/{expected}帧')
        finally:cap.release()
        if not count:raise HTTPException(422,'视频没有可解码画面')
        sid=folder.name;s={'id':sid,'folder':folder,'width':width,'height':height,'frames':count,'fps':fps,'masks':None,'revision':0,'truncated':truncated}
        (folder/'metadata.json').write_text(json.dumps({k:v for k,v in s.items() if k not in ('folder','masks')}),encoding='utf-8')
        with LOCK:SESSIONS[sid]=s
        return {k:s[k] for k in ('id','width','height','frames','fps','truncated')}
    except HTTPException:
        if folder.exists() and folder.name not in SESSIONS:shutil.rmtree(folder)
        raise
    except Exception as e:
        if folder.exists() and folder.name not in SESSIONS:shutil.rmtree(folder)
        raise HTTPException(422,str(e)) from e
    finally:
        await video.close();SLOT.release()

@app.get('/api/frame/{sid}/{frame}.jpg')
def get_frame(sid:str,frame:int):return FileResponse(frame_path(session(sid),frame),media_type='image/jpeg')

@app.post('/api/segment/{sid}')
def segment(sid:str,options:SegmentOptions):
    s=session(sid);storage_check()
    if s['revision']>=5:raise HTTPException(409,'本试验每段最多5次传播，请先检查点位或整理缓存重新导入')
    prompts={};positive=False;total=0
    for key,points in options.prompts.items():
        if not re.fullmatch(r'0|[1-9][0-9]*',key) or int(key)>=s['frames']:raise HTTPException(422,'提示帧无效')
        if not points:continue
        if not any(p.label==1 for p in points):raise HTTPException(422,'每个补点帧都需要至少一个目标内正点，再用负点排除误选')
        for p in points:
            if not math.isfinite(p.x) or not math.isfinite(p.y) or not 0<=p.x<s['width'] or not 0<=p.y<s['height']:raise HTTPException(422,'提示点超出画面')
            positive|=p.label==1;total+=1
        prompts[int(key)]=[p.model_dump() for p in points]
    if not positive or total>200:raise HTTPException(422,'至少需要一个正点，提示点最多200个')
    if not SLOT.acquire(blocking=False):raise HTTPException(409,'已有任务正在运行')
    with LOCK:
        s['revision']+=1;s['masks']=None;rev=s['revision']
    def work(job):
        global ENGINE
        if ENGINE is None:
            from engine import SamEngine
            ENGINE=SamEngine()
        def progress(completed,total):
            with LOCK:JOBS[job]['progress']=.05+.90*completed/max(1,total)
        masks,timings=ENGINE.segment(s['folder']/'frames',prompts,s['frames'],progress_callback=progress)
        clean={}
        for i in range(s['frames']):
            mask=np.asarray(masks[i])
            if mask.shape!=(s['height'],s['width']) or not np.isfinite(mask).all():raise RuntimeError(f'第{i}帧掩码无效')
            clean[i]=(mask>0).astype(np.uint8)
        np.savez_compressed(s['folder']/f'masks-{rev}.npz',**{str(k):v for k,v in clean.items()})
        (s['folder']/f'prompts-{rev}.json').write_text(json.dumps(prompts),encoding='utf-8')
        with LOCK:s['masks']=clean
        return {'timings':timings,'revision':rev,'empty_frames':[i for i,m in clean.items() if not m.any()]}
    return start_job('segment',work)

def start_job(kind,fn):
    jid=uuid.uuid4().hex
    with LOCK:JOBS[jid]={'state':'queued','progress':0,'kind':kind}
    def run():
        start=time.perf_counter()
        try:
            with LOCK:JOBS[jid].update(state='running',progress=.05)
            info=fn(jid)
            with LOCK:JOBS[jid].update(info,state='done',progress=1,seconds=time.perf_counter()-start)
        except Exception as e:
            import traceback;traceback.print_exc()
            with LOCK:JOBS[jid].update(state='error',error=str(e),seconds=time.perf_counter()-start)
        finally:SLOT.release()
    try:threading.Thread(target=run,daemon=True).start()
    except Exception:SLOT.release();raise
    return {'job_id':jid}

@app.get('/api/job/{jid}')
def job(jid:str):
    with LOCK:j=JOBS.get(jid)
    if j is None:raise HTTPException(404,'任务不存在')
    return dict(j)

@app.get('/api/mask/{sid}/{frame}.png')
def mask_image(sid:str,frame:int):
    s=session(sid);frame_path(s,frame);masks_ready(s);mask=s['masks'][frame]
    overlay=np.zeros((*mask.shape,4),np.uint8);overlay[mask>0]=(230,210,20,115)
    ok,buf=cv2.imencode('.png',overlay)
    if not ok:raise HTTPException(500,'掩码编码失败')
    return Response(buf.tobytes(),media_type='image/png',headers={'Cache-Control':'no-store'})

@app.get('/api/preview/{sid}/{frame}.jpg')
def preview(sid:str,frame:int,style:str='mosaic',strength:int=68,padding:int=6):
    s=session(sid);path=frame_path(s,frame);masks_ready(s)
    if style not in STYLES or not 20<=strength<=100 or not 0<=padding<=40:raise HTTPException(422,'样式参数无效')
    image=read_jpeg(path);image=render(image,s['masks'][frame],style,strength,padding)
    ok,buf=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,94])
    if not ok:raise HTTPException(500,'预览编码失败')
    return Response(buf.tobytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store'})

@app.post('/api/export/{sid}')
def export(sid:str,options:ExportOptions):
    s=session(sid);masks_ready(s);storage_check()
    if len(list(s['folder'].glob('export-*.mp4')))>=5:raise HTTPException(409,'本试验每段最多保存5次导出，请停止服务后整理缓存')
    if any(not mask.any() for mask in s['masks'].values()):raise HTTPException(409,'存在空遮罩帧，请补充目标内正点重新传播，当前结果禁止导出')
    if options.style not in STYLES:raise HTTPException(422,'未知样式')
    if not SLOT.acquire(blocking=False):raise HTTPException(409,'已有任务正在运行')
    masks=s['masks'];rev=s['revision'];config=options.model_copy(deep=True)
    def work(jid):
        import av
        from fractions import Fraction
        out=s['folder']/f'export-{jid}.mp4'
        try:
            with av.open(str(out),'w') as mux:
                stream=mux.add_stream('libx264',rate=Fraction(str(s['fps'])).limit_denominator(100000));stream.width=s['width'];stream.height=s['height'];stream.pix_fmt='yuv420p';stream.options={'crf':'18','preset':'fast'}
                for i in range(s['frames']):
                    image=read_jpeg(frame_path(s,i));image=render(image,masks[i],config.style,config.strength,config.padding)
                    for packet in stream.encode(av.VideoFrame.from_ndarray(image,format='bgr24')):mux.mux(packet)
                    with LOCK:JOBS[jid]['progress']=(i+1)/s['frames']
                for packet in stream.encode():mux.mux(packet)
            cap=cv2.VideoCapture(str(out));count=0
            try:
                while cap.read()[0]:count+=1
            finally:cap.release()
            if count!=s['frames']:raise RuntimeError('输出帧数不完整')
            return {'download':f'/api/download/{sid}/{out.name}','frames':count,'revision':rev,'audio':'本次分割原型仅导出无声视频'}
        except Exception:
            if out.exists():out.unlink()
            raise
    return start_job('export',work)

@app.get('/api/download/{sid}/{name}')
def download(sid:str,name:str):
    s=session(sid)
    if not re.fullmatch(r'export-[0-9a-f]{32}\.mp4',name):raise HTTPException(404)
    p=s['folder']/name
    if not p.is_file():raise HTTPException(404)
    return FileResponse(p,media_type='video/mp4',filename='SAM2.1-custom-mask.mp4')

if __name__=='__main__':
    import argparse,socket,uvicorn,webbrowser
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    sock=socket.socket();sock.bind(('127.0.0.1',args.port));sock.listen(128)
    url=f'http://127.0.0.1:{sock.getsockname()[1]}/';(DATA/'service.json').write_text(json.dumps({'pid':os.getpid(),'url':url}),encoding='utf-8');print(url,flush=True)
    if not args.no_browser:threading.Timer(1,lambda:webbrowser.open(url)).start()
    uvicorn.Server(uvicorn.Config(app,log_level='warning',ws='none')).run(sockets=[sock])
