"""Read-only inference latency probe; does not alter application settings."""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import time
import cv2
import numpy as np
from inkshield import server

d = server.get_detector()
print('input', d.input.shape, 'providers', d.session.get_providers(), flush=True)
cap = cv2.VideoCapture(str(server.RUNTIME / 'mask-test-input.mp4'))
ok, frame = cap.read()
cap.release()
assert ok
print('source', frame.shape, flush=True)
for _ in range(2):
    d.detect(frame)
for w, h in [(288, 512), (576, 1024), (1080, 1920)]:
    image = cv2.resize(frame, (w, h))
    samples = []
    for i in range(7):
        start = time.perf_counter()
        boxes = d.detect(image)
        elapsed = (time.perf_counter() - start) * 1000
        if i:
            samples.append(elapsed)
    print(w, h, 'median_ms', round(float(np.median(samples)), 2), 'heads', len(boxes), flush=True)
