"""HyperLPR3 CPU 320 detector only; no OCR or network access.

Geometry follows hyperlpr3 0.1.3 inference/multitask_detect.py (Apache-2.0
package metadata). Weight provenance/limitations: models/HYPERLPR_SOURCE.md.
"""
from pathlib import Path
from .cpu_runtime import session_options

import cv2
import numpy as np
import onnxruntime as ort


class PlateDetector:
    """Return source-pixel (x0, y0, x1, y1, fused_score, 21) tuples.

    Input is a uint8 BGR HWC frame. Class 21 is the application plate ID,
    not either of the detector's internal single/double-layer classes.
    """

    def __init__(self, path):
        options = session_options('plate')
        self.session = ort.InferenceSession(
            Path(path).read_bytes(), sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or inputs[0].shape != [1, 3, 320, 320] or inputs[0].type != "tensor(float)":
            raise ValueError("Expected HyperLPR3 float32 input [1,3,320,320]")
        if not outputs or outputs[0].shape != [1, 6300, 15]:
            raise ValueError("Expected HyperLPR3 output [1,6300,15]")
        self.input_name = inputs[0].name
        self.output_name = outputs[0].name

    @staticmethod
    def _preprocess(frame):
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a uint8 BGR HWC frame")
        height, width = frame.shape[:2]
        if min(height, width) < 1:
            raise ValueError("Frame must not be empty")
        ratio = min(320 / height, 320 / width)
        new_height, new_width = int(height * ratio), int(width * ratio)
        if min(new_height, new_width) < 1:
            raise ValueError("Frame aspect ratio is too extreme for the 320 detector")
        top, left = (320 - new_height) // 2, (320 - new_width) // 2
        resized = cv2.resize(frame, (new_width, new_height))
        padded = cv2.copyMakeBorder(resized, top, 320-new_height-top, left,
                                   320-new_width-left, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        tensor = np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32)[None] / 255.0
        return tensor, ratio, left, top

    @staticmethod
    def _postprocess(raw, ratio, left, top, width, height, threshold):
        """Decode raw [cx,cy,w,h,obj, x1,y1,...,x4,y4,cls0,cls1]."""
        raw = np.asarray(raw)
        if raw.shape != (1, 6300, 15):
            raise ValueError(f"Unexpected HyperLPR3 output shape: {raw.shape}")
        rows = raw[0]
        scores = rows[:, 4] * np.max(rows[:, 13:15], axis=1)
        good = np.isfinite(rows).all(axis=1) & (rows[:, 4] > threshold) & (scores >= threshold)
        rows = rows[good]
        scores = scores[good]
        if len(rows) == 0:
            return []
        boxes = np.concatenate((rows[:, :2] - rows[:, 2:4] / 2,
                                rows[:, :2] + rows[:, 2:4] / 2), axis=1)
        valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
        boxes, rows, scores = boxes[valid], rows[valid], scores[valid]
        order = np.argsort(-scores, kind="stable")
        areas = np.prod(boxes[:, 2:]-boxes[:, :2], axis=1)
        keep = []
        # Class-agnostic NMS: both internal plate types map to one public class.
        while order.size:
            current = order[0]
            keep.append(current)
            rest = order[1:]
            upper = np.maximum(boxes[current, :2], boxes[rest, :2])
            lower = np.minimum(boxes[current, 2:], boxes[rest, 2:])
            intersection = np.prod(np.maximum(lower-upper, 0), axis=1)
            union = areas[current] + areas[rest] - intersection
            iou = intersection / np.maximum(union, np.finfo(np.float32).eps)
            order = rest[iou <= 0.5]
        result = []
        for idx in keep:
            box = boxes[idx].astype(np.float64)
            corners = rows[idx, 5:13].reshape(4, 2).astype(np.float64).copy()
            box[[0, 2]] = np.clip((box[[0, 2]]-left)/ratio, 0, width)
            box[[1, 3]] = np.clip((box[[1, 3]]-top)/ratio, 0, height)
            corners[:, 0] = np.clip((corners[:, 0]-left)/ratio, 0, width)
            corners[:, 1] = np.clip((corners[:, 1]-top)/ratio, 0, height)
            if box[2] > box[0] and box[3] > box[1]:
                result.append((tuple(float(x) for x in box) + (float(scores[idx]), 21), corners))
        return result

    def detect_with_corners(self, frame, threshold=.3):
        """Return (six-column box, predicted 4x2 corners) pairs, not bbox corners.

        Corner order is retained verbatim from the model; unused by first-version
        rectangular masking. No mutable per-frame state is stored on the object.
        """
        threshold = float(threshold)
        if not np.isfinite(threshold) or not 0 <= threshold <= 1:
            raise ValueError("Plate confidence threshold must be in [0,1]")
        tensor, ratio, left, top = self._preprocess(frame)
        raw = self.session.run([self.output_name], {self.input_name: tensor})[0]
        height, width = frame.shape[:2]
        return self._postprocess(raw, ratio, left, top, width, height, threshold)

    def detect(self, frame, threshold=.3):
        return [box for box, _corners in self.detect_with_corners(frame, threshold)]
