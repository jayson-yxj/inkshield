"""Read-only inference latency probe; does not alter application settings."""
import time
import cv2
import numpy as np
import server

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
