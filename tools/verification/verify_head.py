"""Local regression and real-video smoke test. Run from this directory."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import json
import time
from pathlib import Path
import cv2
import numpy as np
from fastapi.testclient import TestClient
from inkshield import server


def main():
    report = {}
    client = TestClient(server.app)
    assert client.get('/').status_code == 200
    health = client.get('/api/health').json()
    assert health['model_ready'], health
    report['health'] = health
    detector = server.get_detector()
    report['inputs'] = [(x.name, x.shape, x.type) for x in detector.session.get_inputs()]
    report['outputs'] = [(x.name, x.shape, x.type) for x in detector.session.get_outputs()]
    # Verify class filtering, threshold, box mapping and raw BGR input contract.
    class FakeSession:
        def run(self, outputs, feed):
            tensor = next(iter(feed.values()))
            assert tensor.dtype == np.float32 and tensor.shape == (1, 3, 100, 200)
            assert tensor[0, 0, 0, 0] == 10 and tensor[0, 2, 0, 0] == 30
            return [np.array([[[7, .1, .2, .4, .6, .9], [12, .1, .2, .4, .6, .99],
                               [7, 0, 0, 1, 1, .1], [7, .8, .8, .7, .7, .9]]], dtype=np.float32)]
    class FakeInput:
        name = 'images'
        shape = [1, 3, 'height', 'width']
    fake = object.__new__(server.HeadDetector)
    fake.session, fake.input, fake.output_name = FakeSession(), FakeInput(), 'boxes'
    synthetic = np.full((100, 200, 3), (10, 20, 30), dtype=np.uint8)
    heads = fake.detect(synthetic)
    assert len(heads) == 1 and np.allclose(heads[0][:4], [20, 20, 80, 60])
    # Expanded masks must clip safely, leave distant pixels untouched and change ROI.
    frame = np.random.default_rng(4).integers(0, 256, (100, 100, 3), dtype=np.uint8)
    original = frame.copy()
    server.apply_masks(frame, [(0, 0, 40, 40, .9, 7)], 68)
    assert not np.array_equal(frame[:40, :40], original[:40, :40])
    assert np.array_equal(frame[70:, 70:], original[70:, 70:])
    assert client.get('/api/download/unknown').status_code == 404
    assert client.post('/api/process', files={'video': ('bad.mp4', b'bad')}, data={'target': 'unknown'}).status_code == 422
    # Invalid input must terminate with an error and must not permit downloading partial output.
    bad = client.post('/api/process', files={'video': ('bad.mp4', b'bad')}, data={'target': 'head'}).json()
    deadline = time.monotonic() + 20
    while True:
        status = client.get(bad['status']).json()
        if status['state'] == 'error':
            break
        assert time.monotonic() < deadline, status
        time.sleep(.1)
    assert client.get(f"/api/download/{bad['job_id']}").status_code == 409
    sample = Path(r'D:\xwechat_files\wxid_kni8lsnnguq522_4a02\msg\video\2026-10\5ebc978a3da7170a344041a99fb89d30.mp4')
    with sample.open('rb') as video:
        response = client.post('/api/process', files={'video': ('sample.mp4', video, 'video/mp4')}, data={'target': 'head', 'strength': 68})
    assert response.status_code == 200, response.text
    job = response.json()
    start = time.monotonic()
    preview_seen = False
    deadline = start + 1200
    while True:
        status = client.get(job['status']).json()
        if status['frame'] and not preview_seen:
            preview_seen = client.get(job['preview']).status_code == 200
        if status['state'] in ('done', 'error'):
            break
        assert time.monotonic() < deadline, status
        time.sleep(.5)
    assert status['state'] == 'done', status
    assert preview_seen
    result = client.get(status['download'])
    assert result.status_code == 200 and len(result.content) > 1000
    output = server.RUNTIME / job['job_id'] / 'output.mp4'
    cap = cv2.VideoCapture(str(output))
    assert cap.isOpened()
    decoded = 0
    while True:
        ok, image = cap.read()
        if not ok:
            break
        decoded += 1
        if decoded == 1:
            ok, data = cv2.imencode('.jpg', image)
            assert ok
            (server.RUNTIME / 'head-sample-preview.jpg').write_bytes(data.tobytes())
    cap.release()
    original_cap = cv2.VideoCapture(str(sample))
    expected_frames = int(original_cap.get(cv2.CAP_PROP_FRAME_COUNT))
    original_cap.release()
    assert decoded == status['frames'] == expected_frames, (decoded, expected_frames, status)
    assert status['frames_without_heads'] < decoded, 'No heads detected anywhere in sample'
    report.update(status=status, decoded_frames=decoded, preview_during_processing=preview_seen,
                  elapsed_seconds=round(time.monotonic() - start, 2), output=str(output), bytes=len(result.content))
    (server.RUNTIME / 'head-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
