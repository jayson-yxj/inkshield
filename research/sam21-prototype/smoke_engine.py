"""Real Desktop/5.mp4 smoke: positive middle-frame click, then correction."""
import json
import os
from pathlib import Path
import time
import cv2
import numpy as np
from engine import SamEngine, SegmentationCancelled

root = Path(__file__).parent
frames = root / "smoke-frames-five"
frames.mkdir(exist_ok=True)
source = Path(os.environ["USERPROFILE"]) / "Desktop" / "5.mp4"
cap = cv2.VideoCapture(str(source))
if not cap.isOpened():
    raise RuntimeError(f"Cannot open {source}")
for idx in range(5):
    ok, image = cap.read()
    if not ok:
        raise RuntimeError(f"Failed decoding {idx}")
    # Frame 646,218 is a face center on original 1280x720 image.
    image = cv2.resize(image, (640, 360), interpolation=cv2.INTER_AREA)
    encoded, data = cv2.imencode(".jpg", image)
    if not encoded:
        raise RuntimeError("JPEG encoding failed")
    (frames / f"{idx:05d}.jpg").write_bytes(data.tobytes())
cap.release()
engine = SamEngine()
assert engine._predictor is None
masks, timings = engine.segment(frames, {2: [{"x": 323, "y": 109, "label": 1}]}, 5)
assert set(masks) == set(range(5))
for mask in masks.values():
    assert mask.shape == (360, 640) and mask.dtype == np.uint8
    assert set(np.unique(mask)).issubset({0, 1})
corrected, correction_timings = engine.segment(frames, {
    2: [{"x": 323, "y": 109, "label": 1}],
    4: [{"x": 323, "y": 109, "label": 1}, {"x": 20, "y": 20, "label": 0}],
}, 5)
assert set(corrected) == set(range(5))
assert corrected[4][109, 323] == 1 and corrected[4][20, 20] == 0
cancelled = False
try:
    engine.segment(frames, {2: [{"x": 323, "y": 109, "label": 1}]}, 5, cancel_callback=lambda: True)
except SegmentationCancelled:
    cancelled = True
assert cancelled
areas = {str(k): int(v.sum()) for k, v in masks.items()}
corrected_areas = {str(k): int(v.sum()) for k, v in corrected.items()}
base = cv2.imdecode(np.frombuffer((frames / "00002.jpg").read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
overlay = base.copy()
overlay[masks[2] > 0] = (0, 180, 255)
ok, encoded = cv2.imencode(".jpg", cv2.addWeighted(base, 0.6, overlay, 0.4, 0))
assert ok
(root / "smoke-mask-overlay.jpg").write_bytes(encoded.tobytes())
np.savez_compressed(root / "smoke-masks.npz", **{str(k): v for k, v in masks.items()})
result = {"source": str(source), "input_dimensions": [640, 360], "frames": 5,
          "initial": timings, "correction": correction_timings,
          "initial_areas": areas, "corrected_areas": corrected_areas,
          "full_bidirectional_coverage": True, "cancellation_checked": cancelled,
          "positive_and_negative_correction_checked": True,
          "accuracy": "Smoke only; no ground truth or quality ranking."}
(root / "engine-smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
