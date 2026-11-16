"""Formal SAM2.1 acceptance against a caller-owned source or packaged service.

No inference is allowed without --inference-slot. --contract-only reads capabilities
and fingerprints only. Use a fresh service --data-dir with sufficient free disk space.
Example: python verify_sam_packaged.py --state STATE --input VIDEO --x 646 --y 218
  --device cpu --inference-slot --output runtime/sam-api-UNIQUE
All coordinates are ORIGINAL pixels. No resizing, model mocks or service shutdown.
"""
from __future__ import annotations

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))


import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output_directory(path, prefix):
    out = Path(path).resolve() if path else ROOT / 'runtime' / (prefix + '-' + time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    return out


def endpoint(args):
    state = json.loads(args.state.read_text(encoding='utf-8')) if args.state else {'url': args.url}
    if args.require_frozen:
        assert state.get('frozen') is True, state
    return state, state['url'].rstrip('/')


def fixture_video(source, destination, frames=5, start_frame=0):
    """Trim with bundled ffmpeg, preserving actual source audio when present."""
    import av
    import imageio_ffmpeg
    with av.open(str(source)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate)
        width, height = stream.width, stream.height
        source_audio = bool(container.streams.audio)
    assert 0 < width <= 1280 and 0 < height <= 720, 'Use original <=1280x720 video; this harness never rescales coordinates'
    assert 1 <= frames <= 150 and start_frame >= 0
    duration = frames / fps
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-nostdin', '-ss', str(start_frame / fps), '-i', str(source),
               '-t', str(duration), '-map', '0:v:0', '-map', '0:a:0?', '-c:v', 'libx264', '-preset', 'ultrafast',
               '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(destination)]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    decoded, audio = decode(destination)
    assert len(decoded) == frames, (len(decoded), frames)
    assert audio == source_audio, 'Fixture must preserve presence of source audio'
    return {'frames': frames, 'fps': fps, 'width': width, 'height': height, 'audio': audio, 'source_start_frame': start_frame}


def decode(path):
    import av
    frames = []
    with av.open(str(path)) as container:
        audio = bool(container.streams.audio)
        for frame in container.decode(video=0):
            frames.append(frame.to_ndarray(format='bgr24'))
    assert frames, 'No decodable video frames: ' + str(path)
    if audio:
        with av.open(str(path)) as container:
            assert sum(frame.samples for frame in container.decode(audio=0)) > 0, 'Audio stream has no decoded samples'
    return frames, audio


def wait_job(client, job_id, desired, timeout=1200):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get('/api/status/' + job_id)
        r.raise_for_status()
        status = r.json()
        assert status['state'] != 'error', status
        if status['state'] == desired:
            return status
        time.sleep(.15)
    raise AssertionError('Timed out waiting for ' + job_id)


def capabilities(client):
    r = client.get('/api/sam/capabilities')
    r.raise_for_status()
    caps = r.json()
    # The service API reports preferred/ready device, overriding engine defaults.
    assert caps['default_device'] in ('cpu', 'cuda'), caps
    deadline = time.monotonic() + 180
    while True:
        warmup = client.get('/api/sam/warmup').json()
        assert warmup['state'] != 'error', warmup
        if warmup['state'] == 'ready': break
        assert time.monotonic() < deadline, warmup
        time.sleep(.2)
    gpu_available = any(d['id']=='cuda' and d['available'] for d in caps['devices'])
    assert warmup['device'] == ('cuda' if gpu_available else 'cpu') or (warmup['device']=='cpu' and warmup.get('fallback_reason')), warmup
    ready_caps = client.get('/api/sam/capabilities').json()
    assert ready_caps['default_device'] == warmup['device'], (ready_caps, warmup)
    caps['verified_warmup'] = warmup
    devices = {d['id']: d for d in caps['devices']}
    assert devices['cpu']['available'] is True and 'cuda' in devices, caps
    if not devices['cuda']['available']:
        assert devices['cuda'].get('reason') or caps.get('reason'), 'Unavailable CUDA needs an actionable reason'
    assert (caps['max_frames'], caps['max_width'], caps['max_height']) == (150, 1280, 720), caps
    return caps


def png_mask(data, width, height, cyan=False):
    import cv2
    import numpy as np
    raw = base64.b64decode(data, validate=True) if isinstance(data, str) else data
    assert raw.startswith(b'\x89PNG\r\n\x1a\n')
    mask = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_UNCHANGED)
    assert mask is not None and mask.shape == (height, width, 4)
    selected = mask[:, :, 3] > 0
    assert selected.any(), 'Model returned an empty mask; choose a clear positive target'
    if cyan:
        assert np.all(mask[selected, :3] == (255, 255, 0)), 'Preview must be cyan BGRA PNG'
    return raw, mask[:, :, 3]


def cache_snapshot(state, job_id):
    if not state.get('data_dir'):
        return None
    folder = Path(state['data_dir']) / 'runtime' / 'sam' / job_id
    assert folder.is_dir(), folder
    return {str(p.relative_to(folder)): {'sha256': sha(p), 'mtime_ns': p.stat().st_mtime_ns}
            for p in folder.rglob('*') if p.is_file()}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    service = p.add_mutually_exclusive_group(required=True)
    service.add_argument('--state', type=Path)
    service.add_argument('--url')
    p.add_argument('--input', '--source', dest='input', type=Path)
    p.add_argument('--x', type=float)
    p.add_argument('--y', type=float)
    p.add_argument('--negative-x', type=float, default=0)
    p.add_argument('--negative-y', type=float, default=0)
    p.add_argument('--start-frame', type=int, default=0)
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    p.add_argument('--output', type=Path)
    p.add_argument('--require-frozen', action='store_true')
    p.add_argument('--contract-only', action='store_true')
    p.add_argument('--inference-slot', action='store_true', help='Set only after parent assigns exclusive inference slot')
    return p


def main():
    args = parser().parse_args()
    if not args.contract_only:
        assert args.inference_slot, 'Parent CPU/GPU slot required; otherwise use --contract-only'
        assert args.input and args.x is not None and args.y is not None, '--input --x --y required'
    out = output_directory(args.output, 'sam-api')
    report = {'status': 'starting', 'device': args.device, 'checks': [], 'output': str(out)}
    try:
        import httpx
        import cv2
        import numpy as np
        state, url = endpoint(args)
        report['service'] = state
        report['source_hashes'] = {name: sha(ROOT / 'src/inkshield' / name) for name in ('server.py', 'sam_service.py', 'sam_engine.py', 'web/index.html')}
        with httpx.Client(base_url=url, timeout=1200, trust_env=False) as client:
            r = client.get('/')
            r.raise_for_status()
            report['served_index_sha256'] = hashlib.sha256(r.content).hexdigest()
            report['capabilities'] = caps = capabilities(client)
            report['checks'].append('capabilities CPU default and explicit CUDA availability/reason')
            if args.contract_only:
                report['status'] = 'contract-only-passed'
                return
            assert caps['available'], caps
            assert any(d['id'] == args.device and d['available'] for d in caps['devices']), 'Selected device unavailable; no fallback permitted'
            fixture = out / 'five-frames.mp4'
            report['fixture'] = meta = fixture_video(args.input, fixture, 5, args.start_frame)
            originals, _ = decode(fixture)
            with fixture.open('rb') as stream:
                r = client.post('/api/media', files={'video': ('sam-fixture.mp4', stream, 'video/mp4')})
            r.raise_for_status()
            media = r.json()
            report['media'] = media
            assert media['frames'] == 5
            # Deliberately nonzero source start: prompt frame=1 means global fixture frame=2.
            body = {'media_id': media['media_id'], 'start_frame': 1, 'end_frame': 4, 'device': args.device}
            positive = {'x': args.x, 'y': args.y, 'label': 1}
            negative = {'x': args.negative_x, 'y': args.negative_y, 'label': 0}
            preview = {**body, 'frame': 1, 'prompts': [positive]}
            invalid = [({'frame': 3}, 'local frame upper bound'), ({'frame': -1}, 'negative frame'),
                       ({'frame': True}, 'boolean frame'), ({'prompts': []}, 'empty points'),
                       ({'prompts': [negative]}, 'negative only'), ({'prompts': [{**positive, 'x': meta['width']}]}, 'x outside'),
                       ({'prompts': [{**positive, 'y': -1}]}, 'negative y'),
                       ({'prompts': [{**positive, 'label': 2}]}, 'invalid label'),
                       ({'device': 'invalid'}, 'invalid device'), ({'end_frame': 1}, 'empty interval')]
            for change, label in invalid:
                response = client.post('/api/sam/preview', json={**preview, **change})
                assert response.status_code == 422, (label, response.status_code, response.text)
            for prompts in ({}, {'3': [positive]}, {'01': [positive]}, {'1': []}, {'1': [negative]}):
                response = client.post('/api/sam/analyze', json={**body, 'prompts': prompts})
                assert response.status_code == 422, (prompts, response.text)
            if not next(d for d in caps['devices'] if d['id'] == 'cuda')['available']:
                response = client.post('/api/sam/preview', json={**preview, 'device': 'cuda'})
                assert response.status_code == 422 and response.json().get('detail'), response.text
                response = client.post('/api/sam/analyze', json={**body, 'device': 'cuda', 'prompts': {'1': [positive]}})
                assert response.status_code == 422, response.text
                report['checks'].append('unavailable CUDA rejected without silent CPU fallback')
            report['checks'].append('strict invalid preview/analyze inputs rejected before inference')
            timings = []
            first_raw = None
            for index, points in enumerate(([positive], [positive], [positive, negative])):
                started = time.perf_counter()
                r = client.post('/api/sam/preview', json={**preview, 'prompts': points})
                r.raise_for_status()
                data = r.json()
                raw, mask = png_mask(data['mask'], meta['width'], meta['height'], cyan=True)
                assert isinstance(data['cache_hit'], bool) and data['seconds'] >= 0
                assert data['cache_hit'] is (index > 0), data
                if index == 0:
                    first_raw = raw
                if index == 1:
                    assert raw == first_raw, 'Identical cached prompts changed actual mask bytes'
                (out / f'preview-{index}.png').write_bytes(raw)
                timings.append({'wall_seconds': time.perf_counter() - started, 'model_seconds': data['seconds'],
                                'cache_hit': data['cache_hit'], 'sha256': hashlib.sha256(raw).hexdigest(), 'area': int(np.count_nonzero(mask))})
            report['preview_timings'] = timings
            report['checks'].append('first click cache miss, repeated/corrected same-frame actual mask cache hits')
            r = client.post('/api/sam/analyze', json={**body, 'prompts': {'1': [positive, negative]}})
            r.raise_for_status()
            job = r.json()['job_id']
            report['analysis_id'] = job
            report['analysis_status'] = status = wait_job(client, job, 'ready')
            assert status['custom'] is True and status['sam_device'] == args.device and status['people'] == [] and status['pending_count'] == 0
            r = client.get('/api/playback/' + job)
            r.raise_for_status()
            playback = r.json()
            assert playback['custom'] is True and playback['sam_device'] == args.device
            assert playback['start_frame'] == 1 and playback['end_frame'] == 4 and playback['frames'] == 3
            assert playback['shapes'] == [[], [], []] and playback['people'] == [] and playback['pending_count'] == 0
            assert playback['custom_mask_url'] and playback['custom_padding'] == 6
            report['playback'] = playback
            masks = []
            for frame in range(3):
                r = client.get(playback['custom_mask_url'].replace('{frame}', str(frame)))
                r.raise_for_status()
                raw, mask = png_mask(r.content, meta['width'], meta['height'])
                (out / f'mask-{frame}.png').write_bytes(raw)
                masks.append(mask)
            snapshot = cache_snapshot(state, job)
            report['cache_before'] = snapshot
            r = client.post('/api/custom-playback/' + job, data={'style':'black','strength':'100'})
            r.raise_for_status()
            protected = wait_job(client, r.json()['job_id'], 'done')
            r = client.get(protected['url']); r.raise_for_status()
            protected_path = out/'protected-browser.mp4'; protected_path.write_bytes(r.content)
            protected_frames, protected_audio = decode(protected_path)
            assert len(protected_frames)==3 and protected_audio==meta['audio']
            import av
            with av.open(str(protected_path)) as container:
                stream=container.streams.video[0]
                assert stream.codec_context.name=='h264' and stream.codec_context.format.name=='yuv420p'
                assert abs(float(stream.average_rate)-meta['fps'])<.01
                if meta['audio']: assert container.streams.audio[0].codec_context.name=='aac'
            for frame, image in enumerate(protected_frames):
                assert image.shape==originals[frame+1].shape
                interior=cv2.erode(masks[frame],np.ones((5,5),np.uint8))>0
                assert interior.any() and float(image[interior].mean())<12
            report['protected_video']={'path':str(protected_path),'frames':3,'codec':'h264','pixel_format':'yuv420p','audio_decoded':protected_audio,'job':protected}
            report['checks'].append('frozen protected browser video encodes and decodes H264/yuv420p with masked pixels and expected audio')
            report['exports'] = []
            for style in ('black', 'mosaic', 'blur', 'boxblur', 'horizontal', 'vertical', 'none'):
                options = {'target': '' if style == 'none' else 'custom', 'style': 'black' if style == 'none' else style, 'strength': '100'}
                previews = []
                for frame in range(3):
                    r = client.get('/api/preview/' + job, params={**options, 'frame': frame})
                    r.raise_for_status()
                    image = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
                    assert image is not None and image.shape == originals[frame + 1].shape
                    previews.append(image)
                # Keep/mute both exercised on real audio; mute all other style exports.
                for muted in ([True, False] if style == 'black' and meta['audio'] else [True]):
                    r = client.post('/api/export/' + job, data={**options, 'muted': str(muted).lower()})
                    r.raise_for_status()
                    exported = wait_job(client, r.json()['job_id'], 'done')
                    assert exported['inference_ms'] == 0, exported
                    assert exported['targets'] == ([] if style == 'none' else ['custom']), exported
                    r = client.get(exported['download'])
                    r.raise_for_status()
                    path = out / (style + ('-mute' if muted else '-audio') + '.mp4')
                    path.write_bytes(r.content)
                    frames, audio = decode(path)
                    assert len(frames) == 3 and audio == (meta['audio'] and not muted)
                    differences = []
                    for frame, image in enumerate(frames):
                        assert image.shape == originals[frame + 1].shape
                        mae = float(np.abs(image.astype(float) - previews[frame].astype(float)).mean())
                        assert mae < 12, (style, frame, mae)
                        differences.append(mae)
                        interior = cv2.erode(masks[frame], np.ones((5, 5), np.uint8)) > 0
                        assert interior.any(), 'Mask has no measurable interior'
                        if style == 'black':
                            assert float(image[interior].mean()) < 12, 'Black export did not apply custom mask'
                        if style == 'none':
                            assert float(np.abs(image.astype(float) - originals[frame + 1].astype(float)).mean()) < 12, 'Empty selection did not preserve source'
                    report['exports'].append({'style': style, 'muted': muted, 'audio_decoded': audio, 'frames': len(frames), 'preview_export_mae': differences})
            assert client.get('/api/playback/' + job).json() == playback, 'Rendering mutated analysis metadata'
            assert cache_snapshot(state, job) == snapshot, 'Rendering changed mask cache bytes/timestamps'
            report['checks'].append('three-frame custom six-style preview/export and empty-target export decode; cache immutable')
            report['audio_coverage'] = 'real keep and mute verified' if meta['audio'] else 'source fixture has no audio; keep-audio not exercised'
            report['status'] = 'passed'
    except Exception:
        report['status'] = 'failed'
        report['error'] = traceback.format_exc()
        raise
    finally:
        (out / 'evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
