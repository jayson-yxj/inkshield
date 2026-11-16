"""Formal SAM API adapter; optional inference imports stay behind explicit calls."""
from __future__ import annotations

import base64
import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, model_validator

SAM_LOCK = threading.Lock()
ENGINES = {}
MIN_FREE_BYTES = 256 * 1024 * 1024
WARMUP_LOCK = threading.Lock()
WARMUP_STATE = {"state":"pending", "device":None, "seconds":0., "error":None, "fallback_reason":None}


class DiskMasks:
    """Immutable manifest; open only the requested frame, never retain mmap handles."""
    def __init__(self, directory, count, shape):
        self.directory, self.count, self.shape = Path(directory), count, shape
        self.signatures = tuple(self._signature(index) for index in range(count))

    def _signature(self, index):
        stat = (self.directory / f'{index}.npy').stat()
        return stat.st_size, stat.st_mtime_ns

    def validate_manifest(self):
        try:
            return self.signatures == tuple(self._signature(index) for index in range(self.count))
        except OSError:
            return False

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if not isinstance(index, int) or not 0 <= index < self.count:
            raise IndexError(index)
        mask = np.load(self.directory / f'{index}.npy', mmap_mode='r', allow_pickle=False)
        if mask.dtype != np.uint8 or mask.shape != self.shape:
            raise HTTPException(409, '自定义遮罩缺失或尺寸无效')
        return mask

    def __iter__(self):
        for index in range(self.count):
            yield self[index]


def require_disk_space(directory, required):
    free = shutil.disk_usage(directory).free
    if free < required + MIN_FREE_BYTES:
        raise HTTPException(507, f'磁盘空间不足：本次预计需要 {required // (1024*1024) + 1} MB，另需保留 256 MB；请释放无用文件后重试，现有分析不会自动删除')


def warmup_status():
    with WARMUP_LOCK:
        return dict(WARMUP_STATE)


def _set_warmup(**values):
    with WARMUP_LOCK:
        WARMUP_STATE.update(values)


def start_warmup():
    """Warm the shared model in the background; automatic startup prefers CUDA."""
    with WARMUP_LOCK:
        if WARMUP_STATE['state'] != 'pending':
            return
        WARMUP_STATE.update(state='warming',device=None)
    def run():
        started = time.perf_counter()
        try:
            with SAM_LOCK:
                from .sam_engine import capabilities
                caps = capabilities()
                if not caps['available']:
                    raise RuntimeError(caps.get('reason') or 'SAM2.1 不可用')
                use_cuda = any(d['id']=='cuda' and d['available'] for d in caps['devices'])
                device = 'cuda' if use_cuda else 'cpu'
                _set_warmup(device=device)
                if use_cuda:
                    try:
                        engine('cuda').warmup()
                    except Exception as exc:
                        ENGINES.clear()
                        _set_warmup(device='cpu',fallback_reason='GPU 预热失败，已降级 CPU：'+str(exc))
                        device = 'cpu'
                        engine('cpu').warmup()
                else:
                    gpu_reason = next((d.get('reason') for d in caps['devices'] if d['id']=='cuda'), None)
                    _set_warmup(fallback_reason=(gpu_reason or '未检测到可用 NVIDIA GPU')+'；使用 CPU')
                    engine('cpu').warmup()
                _set_warmup(state='ready',device=device,seconds=time.perf_counter()-started,error=None)
        except Exception as exc:
            with SAM_LOCK:
                ENGINES.clear()
                _set_warmup(state='error',seconds=time.perf_counter()-started,error=str(exc))
    try:
        threading.Thread(target=run,name='sam-startup-warmup',daemon=True).start()
    except Exception as exc:
        _set_warmup(state='error',error=str(exc))


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: FiniteFloat
    y: FiniteFloat
    label: StrictInt = Field(ge=0, le=1)


class SegmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str = Field(min_length=1)
    start_frame: StrictInt = Field(ge=0)
    end_frame: StrictInt = Field(gt=0)
    device: Literal["cpu", "cuda"] = "cpu"


class PreviewRequest(SegmentRequest):
    frame: StrictInt = Field(ge=0)
    prompts: list[Point] = Field(min_length=1, max_length=256)


class AnalyzeRequest(SegmentRequest):
    prompts: dict[str, list[Point]] = Field(min_length=1, max_length=150)

    @model_validator(mode="after")
    def valid_keys(self):
        if any(not re.fullmatch(r"0|[1-9][0-9]*", key) for key in self.prompts):
            raise ValueError("Prompt frame keys must be canonical local integer indices")
        return self


def engine(device):
    from .sam_engine import SamEngine
    # Keep only one device's heavyweight model resident at a time.
    if device not in ENGINES:
        ENGINES.clear()
        ENGINES[device] = SamEngine(device)
    return ENGINES[device]


def validate(api, request):
    with api.JOB_LOCK:
        media = api.MEDIA.get(request.media_id)
    if media is None:
        raise HTTPException(404, "上传视频不存在")
    try:
        api.validate_frame_range(media["frames"], request.start_frame, request.end_frame)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    count = request.end_frame-request.start_frame
    if isinstance(request, AnalyzeRequest) and count > 150:
        raise HTTPException(422, "SAM2.1 传播最多 150 帧；请先分割片段。单帧点选预览不受片段长度限制")
    if media["width"] > 1280 or media["height"] > 720:
        raise HTTPException(422, "SAM2.1 原始尺寸不得超过 1280x720；请更换视频")
    from .sam_engine import capabilities
    caps = capabilities()
    if not caps["available"]:
        raise HTTPException(503, caps["reason"])
    if not any(d["id"] == request.device and d["available"] for d in caps["devices"]):
        raise HTTPException(422, "所选 SAM 设备不可用；不会自动切换设备")
    prompts = {request.frame: request.prompts} if isinstance(request, PreviewRequest) else {int(k): v for k,v in request.prompts.items()}
    normalized = {}
    for idx, points in prompts.items():
        if not 0 <= idx < count or not points or not any(p.label == 1 for p in points):
            raise HTTPException(422, "每个标注帧必须位于片段内并至少含一个正点")
        if any(not (0 <= p.x < media["width"] and 0 <= p.y < media["height"]) for p in points):
            raise HTTPException(422, "标注点超出原始视频像素范围")
        normalized[idx] = [p.model_dump() for p in points]
    return media.copy(), normalized


def encode_mask(mask, cyan=False):
    rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
    rgba[:,:,:3] = (255,255,0) if cyan else (255,255,255)  # OpenCV BGRA cyan
    rgba[:,:,3] = (mask > 0).astype(np.uint8)*(115 if cyan else 255)
    ok, data = cv2.imencode(".png", rgba)
    if not ok:
        raise RuntimeError("无法编码 SAM 遮罩")
    return data.tobytes()


def require_custom(analysis):
    if isinstance(analysis.custom_masks, DiskMasks):
        masks = analysis.custom_masks
        if (len(masks) != len(analysis.boxes) or masks.shape != (analysis.height, analysis.width) or
                not masks.validate_manifest()):
            raise HTTPException(409, "自定义遮罩缺失或尺寸无效；请重新分析")
        return
    if (not analysis.custom_masks or len(analysis.custom_masks) != len(analysis.boxes) or
        any(m.dtype != np.uint8 or m.shape != (analysis.height, analysis.width) for m in analysis.custom_masks)):
        raise HTTPException(409, "自定义遮罩缺失或尺寸无效；请重新标注并分析后导出")


def apply_custom(frame, mask, strength, style, padding=6):
    """In-place six-style ROI processing shared by preview and export."""
    if mask.shape != frame.shape[:2] or mask.dtype != np.uint8:
        raise RuntimeError("SAM mask is missing or incompatible with source frame")
    if not np.any(mask):
        return
    binary = (mask > 0).astype(np.uint8)
    if padding:
        binary = cv2.dilate(binary, np.ones((padding*2+1,padding*2+1), np.uint8))
    ys, xs = np.nonzero(binary)
    x0,x1,y0,y1 = xs.min(),xs.max()+1,ys.min(),ys.max()+1
    crop = frame[y0:y1,x0:x1]
    h,w = crop.shape[:2]
    strength = max(20,min(100,strength))
    if style == "black" or min(h,w)<8:
        effect = np.zeros_like(crop)
    elif style == "blur":
        sigma = max(2.,min(h,w)*(.08+strength*.003))
        effect = cv2.GaussianBlur(crop,(0,0),sigmaX=sigma,sigmaY=sigma,borderType=cv2.BORDER_REPLICATE)
    elif style in ("boxblur","horizontal","vertical"):
        k = max(3,round(min(h,w)*(.16+strength*.006)) | 1)
        effect = cv2.blur(crop,{"boxblur":(k,k),"horizontal":(k,1),"vertical":(1,k)}[style],borderType=cv2.BORDER_REPLICATE)
    elif style == "mosaic":
        blocks = max(4,int(24-strength*.18))
        sw,sh = max(1,min(w//2,blocks)),max(1,min(h//2,round(blocks*h/w)))
        effect = cv2.resize(cv2.resize(crop,(sw,sh),interpolation=cv2.INTER_AREA),(w,h),interpolation=cv2.INTER_NEAREST)
    else:
        raise ValueError("未知遮罩样式")
    selected = binary[y0:y1,x0:x1] > 0
    crop[selected] = effect[selected]


def install(api):
    from fastapi.exceptions import RequestValidationError
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.responses import JSONResponse

    @api.app.exception_handler(RequestValidationError)
    async def finite_validation_errors(request, exc):
        if request.url.path.startswith("/api/sam/"):
            # FastAPI echoes NaN inputs into JSON errors, causing a secondary 500.
            errors = [{key: item[key] for key in ("type", "loc", "msg") if key in item} for item in exc.errors()]
            return JSONResponse(status_code=422, content={"detail": errors})
        return await request_validation_exception_handler(request, exc)

    @api.app.get("/api/sam/warmup")
    def sam_warmup():
        return warmup_status()

    @api.app.get("/api/sam/capabilities")
    def sam_capabilities():
        from .sam_engine import capabilities
        result = capabilities()
        state = warmup_status()
        result['warmup'] = state
        result['default_device'] = state['device'] if state['state']=='ready' else next((d['id'] for d in reversed(result['devices']) if d['available']), 'cpu')
        return result

    @api.app.post("/api/sam/preview")
    def sam_preview(request: PreviewRequest):
        if not SAM_LOCK.acquire(blocking=False):
            raise HTTPException(429, "SAM 正忙，请稍后重试")
        try:
            media, prompts = validate(api, request)
            cap = cv2.VideoCapture(str(media["input_path"]))
            try:
                if not cap.isOpened():
                    raise RuntimeError("无法打开原始视频")
                api.skip_frames(cap,request.start_frame+request.frame)
                ok, bgr = cap.read()
                if not ok or bgr.shape[:2] != (media["height"],media["width"]):
                    raise RuntimeError("无法解码原始标注帧或尺寸不匹配")
            finally:
                cap.release()
            key = (request.media_id,request.start_frame,request.end_frame,request.device,request.frame)
            mask, timing = engine(request.device).preview(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB),prompts[request.frame],key)
            if mask.shape != (media["height"], media["width"]):
                raise HTTPException(422, "当前帧遮罩尺寸无效，请重新计算")
            return {"mask":base64.b64encode(encode_mask(mask,True)).decode("ascii"),"empty":not bool(np.any(mask)),"width":media["width"],"height":media["height"],**timing}
        except HTTPException:
            raise
        except Exception as exc:
            ENGINES.clear()
            raise HTTPException(503,str(exc)) from exc
        finally:
            SAM_LOCK.release()

    def analyze_worker(job_id, media, request, prompts, job_dir):
        started = time.perf_counter()
        frames_dir = job_dir / "frames"
        cap = None
        published = False
        try:
            frames_dir.mkdir()
            count = request.end_frame-request.start_frame
            api.update(job_id,state="loading")
            cap = cv2.VideoCapture(str(media["input_path"]))
            if not cap.isOpened():
                raise RuntimeError("无法打开原始视频")
            api.skip_frames(cap,request.start_frame)
            for idx in range(count):
                ok, bgr = cap.read()
                if not ok or bgr.shape[:2] != (media["height"],media["width"]):
                    raise RuntimeError(f"SAM 源视频解码失败：本地第 {idx} 帧")
                encoded, data = cv2.imencode(".jpg", bgr)
                if not encoded:
                    raise RuntimeError("SAM 临时帧写入失败")
                (frames_dir / f"{idx:05d}.jpg").write_bytes(data.tobytes())
            cap.release()
            cap = None
            api.update(job_id,state="analyzing")
            def progress(done,total):
                api.update(job_id,frame=done,progress=min(99,round(done/total*100,1)))
            masks,timing = engine(request.device).segment(frames_dir,prompts,count,progress)
            empty_frames = []
            mask_dir = job_dir / "masks"
            mask_dir.mkdir()
            for idx in range(count):
                mask = np.array(masks[idx],dtype=np.uint8,copy=True)
                if mask.shape != (media["height"],media["width"]):
                    raise RuntimeError(f"SAM 第 {idx} 帧遮罩尺寸无效；请重新分析")
                mask = np.frombuffer((mask>0).astype(np.uint8).tobytes(),dtype=np.uint8).reshape(mask.shape)
                np.save(mask_dir / f"{idx}.npy", mask, allow_pickle=False)
                if not np.any(mask):
                    empty_frames.append(idx)
            del masks
            frozen = DiskMasks(mask_dir, count, (media["height"], media["width"]))
            analysis = api.Analysis(media["input_path"],tuple(() for _ in range(count)),media["width"],media["height"],media["fps"],
                start_frame=request.start_frame,face_ids=tuple(() for _ in range(count)),custom_masks=frozen,sam_device=request.device)
            propagation = {"anchor_frames":sorted(prompts),
                           "directions":["forward","backward"] if min(prompts)>0 else ["forward"],
                           "covered_frames":len(frozen),
                           "empty_frame_indices":empty_frames}
            payload = {"custom":True,"sam_device":request.device,"start_frame":request.start_frame,"end_frame":request.end_frame,
                       "frames":count,"width":media["width"],"height":media["height"],"fps":media["fps"],"timing":timing,
                       "sam_propagation":propagation}
            (job_dir / "sam.json").write_text(json.dumps(payload,allow_nan=False),encoding="utf-8")
            with api.JOB_LOCK:
                api.ANALYSES[job_id] = analysis
                api.JOBS[job_id].update(state="ready",progress=100,frame=count,analysis_id=job_id,people=[],pending_count=0,
                    analysis_seconds=round(time.perf_counter()-started,3),sam_timing=timing,sam_propagation=propagation)
                published = True
        except Exception as exc:
            ENGINES.clear()
            api.update(job_id,state="error",error=str(exc))
        finally:
            if cap is not None:
                cap.release()
            shutil.rmtree(frames_dir,ignore_errors=True)
            if not published:
                shutil.rmtree(job_dir,ignore_errors=True)
            SAM_LOCK.release()
            api.ACTIVE_JOBS.release()

    @api.app.post("/api/sam/analyze")
    def sam_analyze(request: AnalyzeRequest):
        if not SAM_LOCK.acquire(blocking=False):
            raise HTTPException(429,"SAM 正忙，请稍后重试")
        acquired = False
        started = False
        job_dir = None
        job_id = None
        try:
            media,prompts = validate(api,request)
            acquired = api.ACTIVE_JOBS.acquire(blocking=False)
            if not acquired:
                raise HTTPException(429,"已有两个活动任务，请等待完成后重试")
            root = api.RUNTIME / "sam"
            root.mkdir(exist_ok=True)
            count = request.end_frame-request.start_frame
            # Results remain available while referenced; capacity is disk-based, not job count.
            require_disk_space(root, count * (media["width"] * media["height"] * 4 + 4096))
            job_id = uuid.uuid4().hex
            job_dir = root / job_id
            job_dir.mkdir()
            count = request.end_frame-request.start_frame
            api.new_job(job_id,"analysis",custom=True,sam_device=request.device,targets=["custom"],
                start_frame=request.start_frame,end_frame=request.end_frame,frames=count,total_frames=count,
                width=media["width"],height=media["height"],fps=media["fps"])
            thread = threading.Thread(target=analyze_worker,args=(job_id,media,request,prompts,job_dir),daemon=True)
            thread.start()
            started = True
            return {"ok":True,"job_id":job_id,"analysis_id":job_id,"status":f"/api/status/{job_id}","custom":True,"sam_device":request.device}
        finally:
            if not started:
                if job_dir is not None:
                    shutil.rmtree(job_dir, ignore_errors=True)
                if job_id is not None and api.require_job_if_present(job_id):
                    api.update(job_id, state="error", error="SAM 任务未能启动")
                if acquired:
                    api.ACTIVE_JOBS.release()
                SAM_LOCK.release()

    @api.app.get("/api/sam/mask/{analysis_id}/{frame}.png")
    def sam_mask(analysis_id: str, frame: int):
        analysis = api.require_analysis(analysis_id)
        require_custom(analysis)
        if frame<0 or frame>=len(analysis.custom_masks):
            raise HTTPException(422,"遮罩帧超出视频范围")
        return Response(encode_mask(analysis.custom_masks[frame]),media_type="image/png",
            headers={"Cache-Control":"private, max-age=31536000, immutable"})
