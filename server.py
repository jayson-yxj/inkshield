from __future__ import annotations

import json
import base64
import re
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from functools import partial
from cpu_runtime import PARALLEL_MODELS, session_options
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app_paths import RESOURCE_ROOT, RUNTIME_ROOT
from mask_timeline import normalize_regions, regions_json, apply_frame_config, require_region_masks
from mask_layers import normalize_layers, layers_json, apply_layers
import sys as _timeline_sys

ROOT = RESOURCE_ROOT
RUNTIME = RUNTIME_ROOT
RUNTIME.mkdir(parents=True, exist_ok=True)
MODEL_PATH = ROOT / "models" / "det_500m.onnx"
RECOGNITION_MODEL_PATH = ROOT / "models" / "w600k_mbf.onnx"
PLATE_MODEL_PATH = Path(os.environ.get("INKSHIELD_PLATE_MODEL", str(ROOT / "models" / "y5fu_320x_sim.onnx")))
HEAD_THRESHOLD = .50
HEAD_PADDING = 0.0
PART_CLASSES = {"face": 16, "plate": 21, "custom": -1}
HUMAN_TARGETS = ("face",)
FaceShape = Literal["inscribed", "circumscribed"]
FACE_SHAPES = ("inscribed", "circumscribed")
MaskStyle = Literal["mosaic", "blur", "black", "boxblur", "horizontal", "vertical"]
MASK_STYLES = ("mosaic", "blur", "black", "boxblur", "horizontal", "vertical")
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_FRAMES = 18000
MAX_ACTIVE_JOBS = 2
MAX_PIXELS = 3840 * 2160
MAX_DIMENSION = 8192
MAX_ACTIVE_PREVIEWS = 2
PREVIEW_SLOTS = threading.BoundedSemaphore(MAX_ACTIVE_PREVIEWS)
JOBS: dict[str, dict] = {}
JOB_LOCK = threading.Lock()
# Model inference is serialized; previews and exports never acquire this lock.
PROCESS_LOCK = threading.Lock()
ACTIVE_JOBS = threading.BoundedSemaphore(MAX_ACTIVE_JOBS)
DETECTOR = None
PLATE_DETECTOR = None
MODEL_LOCK = threading.Lock()


@dataclass(frozen=True)
class Analysis:
    input_path: Path
    boxes: tuple
    width: int
    height: int
    fps: float
    decode_lock: threading.Lock = field(default_factory=threading.Lock, compare=False)
    start_frame: int = 0
    face_ids: tuple = ()
    people: tuple = ()
    pending_count: int = 0
    custom_masks: tuple = ()
    sam_device: str | None = None


ANALYSES: dict[str, Analysis] = {}
MEDIA: dict[str, dict] = {}
app = FastAPI(title="Inkshield local face masking", version="0.11.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"], allow_methods=["*"], allow_headers=["*"])


def get_detector():
    global DETECTOR
    with MODEL_LOCK:
        if DETECTOR is None:
            from face_detector import FaceDetector
            DETECTOR = FaceDetector(MODEL_PATH, RECOGNITION_MODEL_PATH)
    return DETECTOR


def get_plate_detector():
    global PLATE_DETECTOR
    with MODEL_LOCK:
        if PLATE_DETECTOR is None:
            from plate_detector import PlateDetector
            PLATE_DETECTOR = PlateDetector(PLATE_MODEL_PATH)
    return PLATE_DETECTOR


def apply_masks(frame, regions, strength, style="mosaic", context=None, face_shape="circumscribed"):
    """Public compatibility wrapper for cached face and plate boxes."""
    from masking import apply_masks as mask_regions
    return mask_regions(frame, regions, strength, style, context=context, face_shape=face_shape)


def update(job_id, **values):
    with JOB_LOCK:
        JOBS[job_id].update(values)


def require_job(job_id):
    with JOB_LOCK:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="任务不存在")
        return JOBS[job_id].copy()


def require_analysis(analysis_id):
    job = require_job(analysis_id)
    with JOB_LOCK:
        analysis = ANALYSES.get(analysis_id)
    if analysis is None or job["state"] not in ("ready", "done"):
        raise HTTPException(status_code=409, detail="视频分析尚未完成")
    return analysis


def parse_options(target, strength, style):
    targets = ("face", "plate") if target == "all" else (() if target == "" else tuple(dict.fromkeys(part.strip() for part in target.split(","))))
    if any(part not in PART_CLASSES for part in targets):
        raise HTTPException(status_code=422, detail="请选择有效的打码部位：face,plate,custom，可用逗号多选")
    if style not in MASK_STYLES:
        raise HTTPException(status_code=422, detail="未知遮罩样式")
    return targets, max(20, min(100, strength)), style


def parse_face_selection(analysis, face_mode="all", person_ids="", mask_pending=True):
    if face_mode not in ("all", "selected"):
        raise HTTPException(status_code=422, detail="face_mode 必须是 all 或 selected")
    if person_ids.strip():
        tokens = person_ids.split(",")
        if any(not re.fullmatch(r"[1-9][0-9]*", token.strip()) for token in tokens):
            raise HTTPException(status_code=422, detail="person_ids 必须是逗号分隔的正整数")
        ids = frozenset(int(token.strip()) for token in tokens)
    else:
        ids = frozenset()
    if not ids.issubset({person["id"] for person in analysis.people}):
        raise HTTPException(status_code=422, detail="person_ids 包含不属于本次分析的人物")
    return face_mode, ids, mask_pending


def select_regions(boxes, face_ids, targets, face_mode="all", person_ids=frozenset(), mask_pending=True):
    """The single cached-box selection rule used by preview and export."""
    if len(boxes) != len(face_ids):
        raise RuntimeError("Face identity cache is not aligned with boxes")
    selected = {PART_CLASSES[target] for target in targets if target != "custom"}
    return tuple(box for box, person in zip(boxes, face_ids) if box[5] in selected and
                 (box[5] != 16 or face_mode == "all" or
                  (person is None and mask_pending) or person in person_ids))


def new_job(job_id, kind, **values):
    with JOB_LOCK:
        JOBS[job_id] = {"state": "queued", "kind": kind, "progress": 0, "frame": 0,
                        "frames": 0, "total_frames": 0, "width": 0, "height": 0, "fps": 0,
                        "heads": 0, "regions": 0, "frames_without_heads": 0,
                        "frames_without_regions": 0, "people": [], "pending_count": 0, "job_id": job_id,
                        "face_shape": "circumscribed", "face_shapes": list(FACE_SHAPES), "plate_shape": "rectangle", **values}


def video_metadata(cap):
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps <= 0:
        fps = 25.0
    reported = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    total = int(reported) if math.isfinite(reported) and reported > 0 else 0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        raise RuntimeError("视频尺寸无效")
    if width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
        raise RuntimeError(f"视频尺寸超过上限：最多 {MAX_PIXELS} 像素，单边不超过 {MAX_DIMENSION}")
    if total > MAX_FRAMES:
        raise RuntimeError(f"视频超过 {MAX_FRAMES} 帧上限")
    return fps, total, width, height


def validate_frame_range(total, start_frame=0, end_frame=None):
    """Return the global exclusive end; unknown frame counts allow open-ended decoding."""
    if start_frame < 0 or (end_frame is not None and end_frame <= start_frame):
        raise ValueError("分析帧范围无效：需要 0 <= start_frame < end_frame（不含结束帧）")
    if total and (start_frame >= total or (end_frame is not None and end_frame > total)):
        raise ValueError(f"分析帧范围超出视频范围：视频共 {total} 帧")
    return total if end_frame is None and total else end_frame


def skip_frames(cap, count):
    """Decode sequentially rather than seek so segment inference starts frame accurately."""
    for index in range(count):
        # grab still decodes in order (including inter-frame dependencies), but
        # skips BGR conversion/allocation for frames outside the requested range.
        if not cap.grab():
            raise RuntimeError(f"原视频提前停止解码：无法跳过到第 {count} 帧，实际 {index} 帧")


def analyze_video(job_id: str, input_path: Path, threshold: float = HEAD_THRESHOLD,
                  start_frame: int = 0, end_frame: int | None = None):
    """Detect every supported part once in the requested segment; publish an immutable cache."""
    cap = None
    full_source = start_frame == 0 and end_frame is None
    requested_at = time.perf_counter()
    try:
        with PROCESS_LOCK, ExitStack() as resources:
            loading_at = time.perf_counter()
            update(job_id, state="loading", threshold=threshold)
            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                raise RuntimeError("无法打开输入视频")
            fps, total, width, height = video_metadata(cap)
            end_frame = validate_frame_range(total, start_frame, end_frame)
            segment_frames = end_frame - start_frame if end_frame is not None else 0
            skip_frames(cap, start_frame)
            detector = get_detector()
            plate_detector = get_plate_detector()
            # One in-flight frame, one plate worker; drain it even on failure.
            executor = resources.enter_context(ThreadPoolExecutor(max_workers=1, thread_name_prefix='plate')) if PARALLEL_MODELS else None
            def timed_detect(fn, *args, **kwargs):
                started_at = time.perf_counter()
                result = fn(*args, **kwargs)
                return result, time.perf_counter() - started_at
            update(job_id, state="analyzing", total_frames=segment_frames, frames=segment_frames,
                   start_frame=start_frame, end_frame=end_frame, width=width, height=height, fps=fps)
            from identity_gallery import IdentityGallery
            gallery = IdentityGallery()
            people = {}
            identity_frames = []
            pending_count = 0
            frames = []
            inference_time = 0.0
            decode_time = human_time = plate_time = 0.0
            missed = 0
            started = time.perf_counter()
            while full_source or end_frame is None or len(frames) < segment_frames:
                decode_at = time.perf_counter()
                ok, frame = cap.read()
                decode_time += time.perf_counter() - decode_at
                if not ok:
                    break
                if len(frames) >= MAX_FRAMES:
                    raise RuntimeError(f"视频超过 {MAX_FRAMES} 帧上限")
                if frame.shape[:2] != (height, width):
                    raise RuntimeError("视频帧尺寸发生变化")
                before = time.perf_counter()
                plate_future = executor.submit(timed_detect, plate_detector.detect, frame, threshold=threshold) if executor else None
                detections, human_elapsed = timed_detect(detector.detect, frame, HUMAN_TARGETS, threshold=threshold)
                if plate_future is not None:
                    plates, plate_elapsed = plate_future.result()
                else:
                    plates, plate_elapsed = timed_detect(plate_detector.detect, frame, threshold=threshold)
                human_time += human_elapsed
                plate_time += plate_elapsed
                qualities = [face.det_score >= .70 and min(face.bbox[2]-face.bbox[0], face.bbox[3]-face.bbox[1]) >= 40 for face in detections]
                matches = gallery.update([face.normed_embedding for face in detections], qualities)
                frame_ids = []
                for face, match in zip(detections, matches):
                    person = match['person']
                    frame_ids.append(person)
                    if person is None:
                        pending_count += 1
                    else:
                        if person not in people:
                            encoded, thumbnail = cv2.imencode('.jpg', face.thumbnail_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
                            if not encoded:
                                raise RuntimeError('无法编码人物缩略图')
                            people[person] = {'id': person, 'count': 0, 'thumbnail': base64.b64encode(thumbnail.tobytes()).decode('ascii')}
                        people[person]['count'] += 1
                frame_ids.extend([None] * len(plates))
                identity_frames.append(tuple(frame_ids))
                detections = [(*face.bbox, face.det_score, PART_CLASSES['face']) for face in detections] + plates
                inference_time += time.perf_counter() - before
                boxes = tuple(tuple(float(v) if i < 5 else int(v) for i, v in enumerate(box)) for box in detections)
                frames.append(boxes)
                heads = sum(box[5] == PART_CLASSES["face"] for box in boxes)
                missed += int(not heads)
                count = len(frames)
                update(job_id, frame=count, progress=min(99, round(count / segment_frames * 100, 1)) if segment_frames else 0,
                       heads=heads, regions=len(boxes), frames_without_heads=missed,
                       inference_ms=round(inference_time / count * 1000, 2))
            count = len(frames)
            if not count:
                raise RuntimeError("视频中没有可解码的视频帧")
            if segment_frames and count < segment_frames:
                raise RuntimeError(f"视频提前停止解码：预期 {segment_frames} 帧，实际 {count} 帧；结果不作为完整分析")
            end_frame = start_frame + count
            analysis = Analysis(input_path, tuple(frames), width, height, fps, start_frame=start_frame,
                                face_ids=tuple(identity_frames), people=tuple(people.values()), pending_count=pending_count)
            payload = {"version": 3, "analysis_id": job_id, "frames": count, "width": width,
                       "start_frame": start_frame, "end_frame": end_frame,
                       "height": height, "fps": fps, "threshold": threshold, "part_classes": PART_CLASSES,
                       "box_format": ["x0", "y0", "x1", "y1", "score", "classid"], "detections": analysis.boxes,
                       "face_ids": analysis.face_ids, "people": analysis.people, "pending_count": pending_count}
            cache_dir = RUNTIME / job_id
            cache_dir.mkdir(exist_ok=True)
            cache_path = cache_dir / "detections.json"
            temporary = cache_path.with_suffix(".json.tmp")
            with temporary.open("w", encoding="utf-8") as out:
                json.dump(payload, out, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            os.replace(temporary, cache_path)
            # Cache publication and readiness are one atomic state transition.
            with JOB_LOCK:
                ANALYSES[job_id] = analysis
                JOBS[job_id].update(state="ready", progress=100, frames=count, total_frames=count,
                                    frame=count, start_frame=start_frame, end_frame=end_frame,
                                    analysis_id=job_id, people=list(analysis.people), pending_count=pending_count, analysis_seconds=round(time.perf_counter() - started, 3),
                                    timing_ms={"queue": round((loading_at-requested_at)*1000, 2),
                                               "setup": round((started-loading_at)*1000, 2),
                                               "decode": round(decode_time*1000, 2),
                                               "human": round(human_time*1000, 2),
                                               "plate": round(plate_time*1000, 2),
                                                "inference_wall": round(inference_time*1000, 2)},
                                     cpu_mode="parallel" if PARALLEL_MODELS else "serial",
                                    analysis_fps=round(count / max(time.perf_counter()-started, 1e-9), 2))
            return analysis
    finally:
        if cap is not None:
            cap.release()


def export_video(job_id: str, analysis: Analysis, output_path: Path, targets, strength, style, muted=True, face_mode="all", person_ids=frozenset(), mask_pending=True, face_shape="circumscribed", *, preview_mode=False, mask_regions=None, layers=None):
    regions_config = mask_regions if isinstance(mask_regions, tuple) else normalize_regions(
        mask_regions, analysis, targets=targets, strength=strength, style=style,
        face_mode=face_mode, person_ids=person_ids, mask_pending=mask_pending, face_shape=face_shape)
    if layers is None:
        require_region_masks(analysis, regions_config)
    cap = writer = None
    completed = False
    encoded_width = analysis.width + (analysis.width % 2 if preview_mode else 0)
    encoded_height = analysis.height + (analysis.height % 2 if preview_mode else 0)
    video_path = output_path if muted else output_path.with_name('video-only.mp4')
    try:
        update(job_id, state="processing", frames=len(analysis.boxes), total_frames=len(analysis.boxes),
               width=analysis.width, height=analysis.height, fps=analysis.fps,
               start_frame=analysis.start_frame, end_frame=analysis.start_frame + len(analysis.boxes))
        cap = cv2.VideoCapture(str(analysis.input_path))
        if not cap.isOpened():
            raise RuntimeError("无法打开原始视频")
        skip_frames(cap, analysis.start_frame)
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), analysis.fps, (encoded_width, encoded_height))
        if not writer.isOpened():
            raise RuntimeError("无法创建输出视频")
        missed = missed_heads = 0
        started = time.perf_counter()
        for index, boxes in enumerate(analysis.boxes):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f"原视频提前停止解码：预期 {len(analysis.boxes)} 帧，实际 {index} 帧")
            if frame.shape[:2] != (analysis.height, analysis.width):
                raise RuntimeError("原视频帧尺寸与分析缓存不一致")
            region_count = (apply_frame_config(_timeline_sys.modules[__name__], frame, analysis, index, regions_config) if layers is None
                            else apply_layers(_timeline_sys.modules[__name__], frame, index, layers))
            heads = sum(box[5] == PART_CLASSES["face"] for box in boxes)
            missed += int(not region_count)
            missed_heads += int(not heads)
            if preview_mode and (encoded_width != analysis.width or encoded_height != analysis.height):
                frame = cv2.copyMakeBorder(frame, 0, encoded_height - analysis.height,
                                          0, encoded_width - analysis.width, cv2.BORDER_CONSTANT, value=0)
            writer.write(frame)
            update(job_id, frame=index + 1, progress=min(99, round((index + 1) / len(analysis.boxes) * 100, 1)),
                   heads=heads, regions=region_count, frames_without_regions=missed, frames_without_heads=missed_heads)
        # Extra source frames are expected for partial analyses. For a full-source
        # cache retain the original completeness check against source metadata.
        source_total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if analysis.start_frame == 0 and source_total == len(analysis.boxes):
            extra, _ = cap.read()
            if extra:
                raise RuntimeError("原视频帧数超过分析缓存，拒绝导出不完整结果")
        writer.release()
        writer = None
        audio_present = False
        if not muted:
            from audio_export import mux_segment_audio
            audio_present = mux_segment_audio(video_path, analysis.input_path, output_path,
                analysis.start_frame / analysis.fps, len(analysis.boxes) / analysis.fps)
        check = cv2.VideoCapture(str(output_path))
        try:
            if not check.isOpened():
                raise RuntimeError("无法重新打开输出视频进行校验")
            decoded = 0
            while True:
                valid, decoded_frame = check.read()
                if not valid:
                    break
                if decoded_frame.shape[:2] != (encoded_height, encoded_width):
                    raise RuntimeError("输出校验失败：视频尺寸不一致")
                decoded += 1
            if decoded != len(analysis.boxes):
                raise RuntimeError(f"输出校验失败：写入 {len(analysis.boxes)} 帧，实际可解码 {decoded} 帧")
        finally:
            check.release()
        if preview_mode:
            update(job_id, state="processing", progress=95, audio_present=audio_present,
                   source_width=analysis.width, source_height=analysis.height,
                   width=encoded_width, height=encoded_height, inference_ms=0, muted=False)
        else:
            update(job_id, state="done", progress=100, download=f"/api/download/{job_id}",
                   export_seconds=round(time.perf_counter() - started, 3), inference_ms=0,
                   muted=muted, audio_present=audio_present)
        completed = True
    finally:
        if cap is not None:
            cap.release()
        if writer is not None:
            writer.release()
        if video_path != output_path:
            video_path.unlink(missing_ok=True)
        if not completed:
            output_path.unlink(missing_ok=True)


def process_video(job_id: str, input_path: Path, output_path: Path, targets: tuple[str, ...], strength: int, style: str, face_shape="circumscribed"):
    """Legacy callable: analyze all parts once, then export from that cache."""
    try:
        analysis = analyze_video(job_id, input_path)
        export_video(job_id, analysis, output_path, targets, strength, style, face_shape=face_shape)
    except Exception as exc:
        update(job_id, state="error", error=str(exc))


def run_worker(operation, *args):
    try:
        operation(*args)
    except Exception as exc:
        update(args[0], state="error", error=str(exc))
    finally:
        ACTIVE_JOBS.release()


def start_worker(operation, *args):
    thread = threading.Thread(target=run_worker, args=(operation, *args), daemon=True)
    thread.start()


def inspect_video(input_path):
    cap = cv2.VideoCapture(str(input_path))
    try:
        if not cap.isOpened():
            raise RuntimeError("无法打开输入视频")
        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        if not math.isfinite(raw_fps) or raw_fps <= 0:
            raise RuntimeError("无法读取有效视频帧率")
        fps, frames, width, height = video_metadata(cap)
        if not frames:
            raise RuntimeError("无法读取视频帧数或视频没有帧")
        return {"frames": frames, "fps": fps, "width": width, "height": height}
    finally:
        cap.release()


async def receive_video(video, kind, targets=("face",), strength=68, style="mosaic", threshold=HEAD_THRESHOLD,
                        start_frame=0, end_frame=None, media_id=None, face_shape="circumscribed"):
    acquired = False
    worker_started = False
    job_id = None
    requested_end = end_frame
    try:
        if kind != "media" and (not MODEL_PATH.is_file() or not RECOGNITION_MODEL_PATH.is_file()):
            raise HTTPException(status_code=503, detail="人脸检测模型尚未准备好")
        if kind != "media" and not PLATE_MODEL_PATH.is_file():
            raise HTTPException(status_code=503, detail="HyperLPR3 车牌检测模型尚未准备好")
        acquired = ACTIVE_JOBS.acquire(blocking=False)
        if not acquired:
            raise HTTPException(status_code=429, detail="已有两个活动任务，请等待完成后重试")
        job_id = uuid.uuid4().hex
        job_dir = RUNTIME / job_id
        job_dir.mkdir()
        input_path = job_dir / "input.mp4"
        size = 0
        from starlette.concurrency import run_in_threadpool
        def save_upload():
            nonlocal size
            with input_path.open("wb") as out:
                while True:
                    chunk = video.file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="视频上传不得超过 512MB")
                    out.write(chunk)
            if not size:
                raise HTTPException(status_code=422, detail="上传视频为空")
        if media_id is not None:
            if video is not None:
                raise HTTPException(status_code=422, detail="video 与 media_id 只能提供一个")
            with JOB_LOCK:
                media = MEDIA.get(media_id)
            if media is None:
                raise HTTPException(status_code=404, detail="上传视频不存在")
            input_path = media["input_path"]
            metadata = {key: media[key] for key in ("frames", "fps", "width", "height")}
        else:
            if video is None:
                raise HTTPException(status_code=422, detail="需要上传 video 或提供 media_id")
            await run_in_threadpool(save_upload)
            try:
                metadata = await run_in_threadpool(inspect_video, input_path)
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            end_frame = validate_frame_range(metadata["frames"], start_frame, end_frame)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if kind == "media":
            with JOB_LOCK:
                MEDIA[job_id] = {"input_path": input_path, **metadata}
            return {"ok": True, "media_id": job_id, **metadata}
        local_frames = end_frame - start_frame
        new_job(job_id, kind, targets=list(targets), style=style, strength=strength, shape="ellipse", face_shape=face_shape, threshold=threshold,
                start_frame=start_frame, end_frame=end_frame, frames=local_frames, total_frames=local_frames,
                width=metadata["width"], height=metadata["height"], fps=metadata["fps"])
        if kind == "analysis":
            start_worker(analyze_video, job_id, input_path, threshold, start_frame, requested_end)
        else:
            start_worker(process_video, job_id, input_path, job_dir / "output.mp4", targets, strength, style, face_shape)
        worker_started = True
        return {"ok": True, "job_id": job_id, "analysis_id": job_id, "status": f"/api/status/{job_id}",
                "preview": f"/api/preview/{job_id}", "start_frame": start_frame, "end_frame": end_frame,
                "frames": local_frames}
    except BaseException:
        # Remove only this failed upload, never earlier runtime directories.
        if job_id is not None and not worker_started:
            failed_input = RUNTIME / job_id / "input.mp4"
            failed_input.unlink(missing_ok=True)
            if require_job_if_present(job_id):
                update(job_id, state="error", error="任务未能启动")
        raise
    finally:
        if acquired and not worker_started:
            ACTIVE_JOBS.release()
        if video is not None:
            await video.close()


def require_job_if_present(job_id):
    with JOB_LOCK:
        return job_id in JOBS


@app.get("/")
def index():
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-cache"})


@app.get('/workspace_ui.js')
@app.get('/workspace_ui.css')
@app.get('/layers_ui.js')
def workspace_asset(request: Request):
    name = request.url.path.rsplit('/', 1)[-1]
    if name not in ('workspace_ui.js', 'workspace_ui.css', 'layers_ui.js') or not (ROOT / name).is_file():
        raise HTTPException(404, '资源不存在')
    return FileResponse(ROOT / name, media_type='text/css' if name.endswith('.css') else 'text/javascript',
                        headers={'Cache-Control': 'no-cache'})


@app.get("/startup")
def startup():
    return FileResponse(ROOT / "splash-preview.html", headers={"Cache-Control": "no-store"})


@app.get("/tutorial")
def tutorial():
    return FileResponse(ROOT / "tutorial-preview.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
def health():
    try:
        detector = get_detector()
        get_plate_detector()
        return {"ok": True, "model_ready": True, "model": MODEL_PATH.name, "class_id": 16,
                "recognition_model": RECOGNITION_MODEL_PATH.name, "identity_modes": ["all", "selected"],
                "model_usage": "local noncommercial research",
                "plate_model": PLATE_MODEL_PATH.name, "plate_shape": "rectangle", "plate_ocr": False,
                "threshold": HEAD_THRESHOLD, "padding": HEAD_PADDING, "targets": list(PART_CLASSES),
                "styles": list(MASK_STYLES), "shape": "ellipse", "providers": detector.session.get_providers(),
                "max_upload_bytes": MAX_UPLOAD_BYTES, "max_frames": MAX_FRAMES, "max_active_jobs": MAX_ACTIVE_JOBS,
                "max_pixels": MAX_PIXELS, "max_dimension": MAX_DIMENSION, "max_active_previews": MAX_ACTIVE_PREVIEWS,
                "face_shape": "circumscribed", "face_shapes": list(FACE_SHAPES)}
    except Exception as exc:
        return {"ok": False, "model_ready": False, "model": MODEL_PATH.name, "error": str(exc)}


@app.post("/api/media")
async def upload_media(video: UploadFile = File(...)):
    """Save the original upload and inspect metadata without loading or running models."""
    return await receive_video(video, "media")


@app.post("/api/analyze")
async def analyze(video: UploadFile | None = File(None), threshold: float = Form(HEAD_THRESHOLD, ge=0.05, le=0.95),
                  start_frame: int = Form(0, ge=0), end_frame: int | None = Form(None, ge=1),
                  media_id: str | None = Form(None)):
    return await receive_video(video, "analysis", threshold=threshold, start_frame=start_frame,
                               end_frame=end_frame, media_id=media_id)


@app.post("/api/process")
async def process(request: Request, video: UploadFile = File(...), target: str = Form("face"), strength: int = Form(68), style: MaskStyle = Form("mosaic"), face_shape: FaceShape = Form("circumscribed")):
    try:
        # FastAPI's Form default treats an explicit empty field as missing.
        target = (await request.form()).get("target", target)
        targets, strength, style = parse_options(target, strength, style)
    except HTTPException:
        await video.close()
        raise
    return await receive_video(video, "legacy", targets, strength, style, face_shape=face_shape)


@app.get("/api/status/{job_id}")
def status(job_id: str):
    return require_job(job_id)


@app.get("/api/preview/{analysis_id}")
def preview(analysis_id: str, frame: int = 0, target: str = "face", strength: int = 68, style: MaskStyle = "mosaic",
            face_mode: str = "all", person_ids: str = "", mask_pending: bool = True,
            face_shape: FaceShape = "circumscribed", mask_regions: str | None = None, layers: str | None = None):
    analysis = require_analysis(analysis_id)
    targets, strength, style = parse_options(target, strength, style)
    face_mode, ids, mask_pending = parse_face_selection(analysis, face_mode, person_ids, mask_pending)
    regions_config = normalize_regions(mask_regions, analysis, targets=targets, strength=strength, style=style,
        face_mode=face_mode, person_ids=ids, mask_pending=mask_pending, face_shape=face_shape)
    if layers is not None and mask_regions is not None:
        raise HTTPException(422, "layers 与 mask_regions 不可同时提供")
    layer_config = normalize_layers(_timeline_sys.modules[__name__], analysis, layers) if layers is not None else None
    if layer_config is None:
        require_region_masks(analysis, regions_config)
    if frame < 0 or frame >= len(analysis.boxes):
        raise HTTPException(status_code=422, detail="预览帧超出视频范围")
    # Browser abort does not stop a sync worker: bound decode AND compositing.
    if not PREVIEW_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="已有两个预览正在生成，请稍后重试")
    try:
        # No shared capture, process/model lock, or inference on this path.
        with analysis.decode_lock:
            cap = cv2.VideoCapture(str(analysis.input_path))
            try:
                if not cap.isOpened():
                    raise HTTPException(status_code=409, detail="无法打开原始视频")
                source_frame = analysis.start_frame + frame
                if source_frame and not cap.set(cv2.CAP_PROP_POS_FRAMES, source_frame):
                    raise HTTPException(status_code=409, detail="无法定位预览帧")
                ok, image = cap.read()
                if not ok:
                    raise HTTPException(status_code=409, detail="无法解码预览帧")
                if image.shape[:2] != (analysis.height, analysis.width):
                    raise HTTPException(status_code=409, detail="原视频帧尺寸与分析缓存不一致")
            finally:
                cap.release()
        if layer_config is None:
            apply_frame_config(_timeline_sys.modules[__name__], image, analysis, frame, regions_config)
        else:
            apply_layers(_timeline_sys.modules[__name__], image, frame, layer_config)
        encoded, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not encoded:
            raise HTTPException(status_code=500, detail="无法编码预览帧")
        return Response(data.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Frame-Index": str(frame)})
    finally:
        PREVIEW_SLOTS.release()


@app.get("/api/playback/{analysis_id}")
def playback(analysis_id: str):
    """Cached geometry and person IDs; browser decodes the original local blob."""
    from masking import build_shapes
    analysis = require_analysis(analysis_id)
    if not PREVIEW_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="预览繁忙，请稍后重试")
    try:
        geometry = []
        for boxes, face_ids in zip(analysis.boxes, analysis.face_ids):
            shapes = []
            for box, person in zip(boxes, face_ids):
                for shape in build_shapes((box,), context=boxes):
                    shapes.append([*shape, box[5], person])
            geometry.append(shapes)
        payload = {"frames": len(analysis.boxes), "fps": analysis.fps,
                   "start_frame": analysis.start_frame, "end_frame": analysis.start_frame + len(analysis.boxes),
                   "width": analysis.width, "height": analysis.height,
                   "shapes": geometry, "face_shape": "circumscribed", "face_shapes": list(FACE_SHAPES),
                   "plate_shape": "rectangle", "people": analysis.people, "pending_count": analysis.pending_count,
                    "custom": bool(analysis.custom_masks), "sam_device": analysis.sam_device,
                    "custom_padding": 6,
                    "custom_mask_url": f"/api/sam/mask/{analysis_id}/{{frame}}.png" if analysis.custom_masks else None}
        return Response(json.dumps(payload, separators=(",", ":"), allow_nan=False),
                        media_type="application/json", headers={"Cache-Control": "no-store"})
    finally:
        PREVIEW_SLOTS.release()


@app.post("/api/export/{analysis_id}")
async def export(request: Request, analysis_id: str, target: str = Form("face"), strength: int = Form(68), style: MaskStyle = Form("mosaic"), muted: bool = Form(True),
           face_mode: str = Form("all"), person_ids: str = Form(""), mask_pending: bool = Form(True),
                 face_shape: FaceShape = Form("circumscribed")):
    analysis = require_analysis(analysis_id)
    # Inspect raw form: missing timeline is legacy, explicit [] removes all effects.
    form = await request.form()
    target = form.get("target", target)
    raw_regions = form['mask_regions'] if 'mask_regions' in form else None
    targets, strength, style = parse_options(target, strength, style)
    face_mode, ids, mask_pending = parse_face_selection(analysis, face_mode, person_ids, mask_pending)
    regions_config = normalize_regions(raw_regions, analysis, targets=targets, strength=strength, style=style,
        face_mode=face_mode, person_ids=ids, mask_pending=mask_pending, face_shape=face_shape)
    if "layers" in form and "mask_regions" in form:
        raise HTTPException(422, "layers 与 mask_regions 不可同时提供")
    layer_config = normalize_layers(_timeline_sys.modules[__name__], analysis, form["layers"]) if "layers" in form else None
    if layer_config is None:
        require_region_masks(analysis, regions_config)
    if not ACTIVE_JOBS.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="已有两个活动任务，请等待完成后重试")
    job_id = uuid.uuid4().hex
    try:
        job_dir = RUNTIME / job_id
        job_dir.mkdir()
        new_job(job_id, "export", analysis_id=analysis_id, mask_regions=json.loads(regions_json(regions_config)), targets=list(targets), strength=strength, style=style, muted=muted,
                face_mode=face_mode, person_ids=sorted(ids), mask_pending=mask_pending, face_shape=face_shape,
                 people=list(analysis.people), pending_count=analysis.pending_count,
                 shape="ellipse", frames=len(analysis.boxes), total_frames=len(analysis.boxes),
                width=analysis.width, height=analysis.height, fps=analysis.fps,
                start_frame=analysis.start_frame, end_frame=analysis.start_frame + len(analysis.boxes))
        operation = (partial(export_video, layers=layer_config) if layer_config is not None else
                     export_video if raw_regions is None else partial(export_video, mask_regions=regions_config))
        if layer_config is not None:
            update(job_id, layers=json.loads(layers_json(layer_config)))
        start_worker(operation, job_id, analysis, job_dir / "output.mp4", targets, strength, style, muted, face_mode, ids, mask_pending, face_shape)
    except Exception:
        ACTIVE_JOBS.release()
        if require_job_if_present(job_id):
            update(job_id, state="error", error="导出任务未能启动")
        raise
    return {"ok": True, "job_id": job_id, "analysis_id": analysis_id, "status": f"/api/status/{job_id}"}


@app.get("/api/download/{job_id}")
def download(job_id: str):
    if require_job(job_id)["state"] != "done":
        raise HTTPException(status_code=409, detail="输出文件尚未完成")
    return FileResponse(RUNTIME / job_id / "output.mp4", media_type="video/mp4", filename="inkshield-head-output.mp4")


# Optional SAM adapter imports no torch or vendored model during core startup.
import sys as _sys
from sam_service import install as _install_sam
_install_sam(_sys.modules[__name__])
from preview_video import install as _install_preview_video
_install_preview_video(_sys.modules[__name__])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("INKSHIELD_PORT", "8000")), reload=False)
