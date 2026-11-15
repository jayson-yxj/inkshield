"""Browser-decodable custom previews, built only from immutable cached masks."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from fastapi import Form, HTTPException, Request
from mask_timeline import normalize_regions, regions_json, require_region_masks
from mask_layers import normalize_layers, layers_json
import json
from fastapi.responses import FileResponse

ENCODER_VERSION = 1
MAX_CACHED_PREVIEWS = 12


def transcode_browser_video(source: Path, output: Path, analysis, audio_present: bool):
    """Transcode protected pixels only; the original video is never an input."""
    import av
    import imageio_ffmpeg

    log_path = output.with_suffix('.ffmpeg.log')
    try:
        with log_path.open('wb') as log:
            result = subprocess.run([
                imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-y',
                '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '2',
                '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart',
                str(output),
            ], stdin=subprocess.DEVNULL, stdout=log, stderr=log, timeout=600,
               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise RuntimeError('浏览器预览编码失败：' + log_path.read_text(encoding='utf-8', errors='replace')[-2000:])
        expected_size = (analysis.width + analysis.width % 2, analysis.height + analysis.height % 2)
        with av.open(str(output)) as container:
            video = container.streams.video[0]
            if video.codec_context.name != 'h264' or video.codec_context.format.name != 'yuv420p':
                raise RuntimeError('浏览器预览编码格式校验失败')
            if (video.width, video.height) != expected_size:
                raise RuntimeError('浏览器预览尺寸校验失败')
            if abs(float(video.average_rate) - analysis.fps) > .01:
                raise RuntimeError('浏览器预览帧率校验失败')
            if bool(container.streams.audio) != audio_present:
                raise RuntimeError('浏览器预览音轨校验失败')
            if audio_present and container.streams.audio[0].codec_context.name != 'aac':
                raise RuntimeError('浏览器预览音频格式校验失败')
            count = 0
            for frame in container.decode(video):
                if (frame.width, frame.height) != expected_size:
                    raise RuntimeError('浏览器预览解码尺寸不一致')
                count += 1
            if count != len(analysis.boxes):
                raise RuntimeError(f'浏览器预览帧数校验失败：预期 {len(analysis.boxes)}，实际 {count}')
        if audio_present:
            with av.open(str(output)) as container:
                if not any(frame.samples for frame in container.decode(audio=0)):
                    raise RuntimeError('浏览器预览音轨无法解码')
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        log_path.unlink(missing_ok=True)


def install(api):
    # No eviction: URLs already handed to a playing browser remain valid.
    from collections import OrderedDict
    cache = OrderedDict()
    cache_lock = threading.Lock()
    api.CUSTOM_PLAYBACK_CACHE = cache

    def response(job_id, reused):
        job = api.require_job(job_id)
        return {'ok': True, 'job_id': job_id, 'analysis_id': job['analysis_id'],
                'status': f'/api/status/{job_id}', 'state': job['state'],
                'url': job.get('url'), 'reused': reused}

    def generate(job_id, analysis, directory, strength, style, key, regions=None, layers=None):
        protected = directory / 'protected.mp4'
        temporary = directory / 'browser.tmp.mp4'
        output = directory / 'playback.mp4'
        started = time.perf_counter()
        try:
            options = {'layers': layers} if layers is not None else ({} if regions is None else {'mask_regions': regions})
            api.export_video(job_id, analysis, protected, ('custom',), strength, style,
                             muted=False, preview_mode=True, **options)
            audio_present = api.require_job(job_id)['audio_present']
            transcode_browser_video(protected, temporary, analysis, audio_present)
            os.replace(temporary, output)
            api.update(job_id, state='done', progress=100,
                       url=f'/api/custom-playback-video/{job_id}',
                       duration=len(analysis.boxes) / analysis.fps,
                       preview_seconds=round(time.perf_counter() - started, 3))
        except BaseException as exc:
            output.unlink(missing_ok=True)
            api.update(job_id, state='error', error=str(exc), url=None)
            with cache_lock:
                if cache.get(key) == job_id:
                    cache.pop(key)
        finally:
            protected.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)

    @api.app.post('/api/custom-playback/{analysis_id}')
    async def custom_playback(request: Request, analysis_id: str, style: str = Form('mosaic'), strength: int = Form(68)):
        analysis = api.require_analysis(analysis_id)
        _, strength, style = api.parse_options('custom', strength, style)
        form = await request.form()
        raw_regions = form['mask_regions'] if 'mask_regions' in form else None
        regions = normalize_regions(raw_regions, analysis, targets=('custom',), strength=strength, style=style)
        if "layers" in form and "mask_regions" in form:
            raise HTTPException(422, "layers 与 mask_regions 不可同时提供")
        layers = normalize_layers(api, analysis, form["layers"]) if "layers" in form else None
        if layers is None:
            require_region_masks(analysis, regions)
        from sam_service import DiskMasks
        if not isinstance(analysis.custom_masks, DiskMasks) and any(mask.flags.writeable for mask in analysis.custom_masks):
            raise HTTPException(409, '自定义遮罩缓存必须冻结后才能生成连续预览')
        if (not analysis.boxes or len(analysis.face_ids) != len(analysis.boxes) or
            any(len(boxes) != len(ids) for boxes, ids in zip(analysis.boxes, analysis.face_ids))):
            raise HTTPException(409, '分析缓存不完整，无法生成连续预览')
        canonical_regions = regions_json(regions)
        key = (analysis_id, layers_json(layers) if layers is not None else canonical_regions, ENCODER_VERSION, layers is not None)
        with cache_lock:
            existing = cache.get(key)
            if existing:
                job = api.require_job(existing)
                if job['state'] != 'error' and (job['state'] != 'done' or (api.RUNTIME / existing / 'playback.mp4').is_file()):
                    cache.move_to_end(key)
                    return response(existing, True)
                cache.pop(key)
            if len(cache) >= MAX_CACHED_PREVIEWS:
                # Bound the reuse index only. Published URLs and active jobs remain valid.
                for old_key, old_id in list(cache.items()):
                    if api.require_job(old_id)['state'] in ('done', 'error'):
                        cache.pop(old_key)
                        break
            if len(cache) >= MAX_CACHED_PREVIEWS:
                raise HTTPException(429, '连续预览正在生成，请等待完成后重试')
            from sam_service import require_disk_space
            require_disk_space(api.RUNTIME, max(64 * 1024 * 1024, analysis.width * analysis.height * len(analysis.boxes)))
            if not api.ACTIVE_JOBS.acquire(blocking=False):
                raise HTTPException(429, '已有两个活动任务，请等待完成后重试')
            job_id = uuid.uuid4().hex
            directory = api.RUNTIME / job_id
            try:
                directory.mkdir()
                api.new_job(job_id, 'custom-playback', analysis_id=analysis_id,
                            targets=['custom'], style=style, strength=strength, url=None,
                            mask_regions=json.loads(canonical_regions),
                            frames=len(analysis.boxes), total_frames=len(analysis.boxes),
                            fps=analysis.fps, width=analysis.width, height=analysis.height,
                            start_frame=analysis.start_frame,
                            end_frame=analysis.start_frame + len(analysis.boxes))
                cache[key] = job_id
                api.start_worker(generate, job_id, analysis, directory, strength, style, key,
                                 None if raw_regions is None else regions, layers)
            except BaseException:
                cache.pop(key, None)
                api.ACTIVE_JOBS.release()
                if api.require_job_if_present(job_id):
                    api.update(job_id, state='error', error='连续预览任务未能启动', url=None)
                if directory.is_dir():
                    directory.rmdir()
                raise
        return response(job_id, False)

    @api.app.get('/api/custom-playback-video/{job_id}')
    def custom_playback_video(job_id: str):
        job = api.require_job(job_id)
        if job.get('kind') != 'custom-playback':
            raise HTTPException(404, '连续预览不存在')
        if job['state'] != 'done':
            raise HTTPException(409, '连续预览尚未生成完成')
        path = api.RUNTIME / job_id / 'playback.mp4'
        if not path.is_file():
            raise HTTPException(404, '连续预览文件不存在')
        return FileResponse(path, media_type='video/mp4', headers={'Cache-Control': 'no-store'})
