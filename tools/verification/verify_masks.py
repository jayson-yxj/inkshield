"""Ellipse pixel invariants, class selection, API settings and short-video matrix."""

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
    client = TestClient(server.app)
    rng = np.random.default_rng(17)
    original = rng.integers(1, 256, (140, 180, 3), dtype=np.uint8)
    box = (60, 50, 100, 90, .99, 17)
    yy, xx = np.ogrid[:140, :180]
    radius = 20
    expected = ((xx + .5 - 80) / radius) ** 2 + ((yy + .5 - 70) / radius) ** 2 <= 1
    for style in server.MASK_STYLES:
        frame = original.copy()
        server.apply_masks(frame, [box], 68, style)
        assert np.array_equal(frame[~expected], original[~expected]), style
        assert not np.array_equal(frame[expected], original[expected]), style
        if style == 'black':
            assert np.all(frame[65:75, 75:85] == 0)
            # Compare the feather band in aggregate; 8-bit rounding may leave
            # individual dark channels unchanged near the outermost boundary.
            assert np.any(frame[51:54, 77:83] > 0)
            assert np.any(frame[51:54, 77:83] < original[51:54, 77:83])
        # Inscribed ellipse leaves box corners untouched and reaches side centers.
        assert not expected[50, 60] and not expected[89, 99]
        assert expected[50, 80] and expected[70, 60]
        assert np.array_equal(frame[:50], original[:50])
        assert np.array_equal(frame[90:], original[90:])
        clipped = original.copy()
        server.apply_masks(clipped, [(-15, -20, 25, 30, .99, 7)], 68, style)
        assert np.array_equal(clipped[100:], original[100:])
        assert not np.array_equal(clipped[:25, :20], original[:25, :20])
    # Tiny regions must never become resize identity, even at weak strength.
    for size in range(1, 12):
        for strength in (20, 68, 100):
            tiny = original.copy()
            server.apply_masks(tiny, [(60, 50, 60 + size, 50 + size, .99, 17)], strength, 'mosaic')
            assert not np.array_equal(tiny[50:50+size, 60:60+size], original[50:50+size, 60:60+size]), (size, strength)
            if size < 8:
                assert np.all(tiny[50 + size//2, 60 + size//2] == 0)
    class Input:
        name = 'input'; shape = [1, 3, 'H', 'W']
    class Session:
        def run(self, outputs, feed):
            return [np.array([[[k, .3, .3, .5, .5, .9] for k in (7, 12, 16, 17, 18, 19, 20)]], np.float32)]
    fake = object.__new__(server.HeadDetector)
    fake.input, fake.session, fake.output_name = Input(), Session(), 'output'
    assert [r[5] for r in fake.detect(original)] == [7]
    assert [r[5] for r in fake.detect(original, ('eyes', 'mouth'))] == [17, 19]
    assert len(fake.detect(original, tuple(server.PART_CLASSES))) == 6
    for data in ({'target': 'head,unknown'}, {'target': ',head'}, {'style': 'unknown'}):
        r = client.post('/api/process', files={'video': ('bad.mp4', b'bad')}, data=data)
        assert r.status_code == 422, r.text
    sample = Path(r'D:\xwechat_files\wxid_kni8lsnnguq522_4a02\msg\video\2026-10\5ebc978a3da7170a344041a99fb89d30.mp4')
    cap = cv2.VideoCapture(str(sample))
    ok, first = cap.read(); assert ok
    clip = server.RUNTIME / 'mask-test-input.mp4'
    writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*'mp4v'), 30, (first.shape[1], first.shape[0]))
    assert writer.isOpened()
    writer.write(first)
    for _ in range(7):
        ok, frame = cap.read(); assert ok; writer.write(frame)
    writer.release(); cap.release()
    reports = []
    for target, style in [('head', 'mosaic'), ('eyes,mouth', 'blur'), ('head,face,eyes,nose,mouth,ears', 'black')]:
        with clip.open('rb') as video:
            r = client.post('/api/process', files={'video': ('clip.mp4', video)}, data={'target': target, 'style': style})
        assert r.status_code == 200, r.text
        job = r.json(); deadline = time.monotonic() + 120
        while True:
            s = client.get(job['status']).json()
            if s['state'] in ('done', 'error'): break
            assert time.monotonic() < deadline, s
            time.sleep(.1)
        assert s['state'] == 'done' and s['frames'] == 8, s
        assert s['style'] == style and s['targets'] == target.split(',') and s['shape'] == 'ellipse'
        assert s['frames_without_regions'] < 8, s
        assert client.get(job['preview']).status_code == 200
        assert client.get(s['download']).status_code == 200
        reports.append(s)
    print(json.dumps({'pixel_and_contract_tests': 'passed', 'real_video_matrix': reports}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
