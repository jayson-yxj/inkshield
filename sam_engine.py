"""Lazy official SAM 2.1 tiny inference. Importing this module never imports torch."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import time
from collections import OrderedDict

from app_paths import RESOURCE_ROOT

MODEL_SHA256 = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
SOURCE_COMMIT = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
MODEL_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt"


def resource_paths():
    return (Path(os.environ.get("INKSHIELD_SAM_MODEL", str(RESOURCE_ROOT / "models" / "sam2.1_hiera_tiny.pt"))),
            Path(os.environ.get("INKSHIELD_SAM_VENDOR", str(RESOURCE_ROOT / "vendor" / "sam2"))))


def capabilities():
    model, vendor = resource_paths()
    available = model.is_file() and (vendor / "sam2" / "build_sam.py").is_file() and importlib.util.find_spec("torch") is not None
    cuda = False
    reason = None
    cuda_reason = "CUDA 运行库未检测到可用 NVIDIA 设备；请选择 CPU"
    if available:
        try:
            import torch
        except Exception as exc:
            available, reason = False, str(exc)
        else:
            try:
                cuda = bool(torch.cuda.is_available())
            except Exception as exc:
                # A broken GPU probe must not hide a working CPU installation.
                cuda_reason = f"CUDA 设备检测失败：{exc}；请选择 CPU"
    else:
        reason = "SAM2.1 optional dependencies, official vendor or model are not installed"
    return {"available": available, "devices": [{"id": "cpu", "label": "CPU", "available": True},
            {"id": "cuda", "label": "NVIDIA CUDA", "available": cuda,
             "reason": None if cuda else cuda_reason}], "default_device": "cpu",
            "max_frames": 150, "max_width": 1280, "max_height": 720, "reason": reason}


class SamEngine:
    def __init__(self, device="cpu"):
        self.device = device
        self._predictor = None
        self.features = OrderedDict()
        self.model_load_seconds = 0.

    def _load(self):
        if self._predictor is None:
            started = time.perf_counter()
            model, vendor = resource_paths()
            if not model.is_file() or not (vendor / "sam2" / "build_sam.py").is_file():
                raise RuntimeError("SAM2.1 official model/vendor missing")
            digest = hashlib.sha256()
            with model.open("rb") as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != MODEL_SHA256:
                raise RuntimeError("SAM2.1 tiny checkpoint SHA256 does not match official weights")
            import torch
            if self.device not in ("cpu", "cuda") or (self.device == "cuda" and not torch.cuda.is_available()):
                raise ValueError("Requested SAM device is unavailable; no fallback was performed")
            torch.set_num_threads(4)
            vendor_path = str(vendor.resolve())
            if vendor_path not in sys.path:
                sys.path.insert(0, vendor_path)
            from sam2.build_sam import build_sam2_video_predictor
            predictor = build_sam2_video_predictor("configs/sam2.1/sam2.1_hiera_t.yaml", str(model),
                device=self.device, hydra_overrides_extra=["++model.fill_hole_area=0"], vos_optimized=False)
            predictor.fill_hole_area = 0
            self._predictor = predictor.float().eval()
            self.model_load_seconds = time.perf_counter() - started
        return self._predictor

    def warmup(self, width=1280, height=720):
        """Warm the shared model and official click path without changing the LRU.

        The service must hold SAM_LOCK while calling this method, just as it does
        for preview/segment. The temporary image predictor shares this model;
        only its synthetic embeddings are discarded, never real frame features.
        """
        if type(width) is not int or type(height) is not int or not (1 <= width <= 1280 and 1 <= height <= 720):
            raise ValueError("Warmup image must be within 1280x720")
        started = time.perf_counter()
        import numpy as np
        first_load = self._predictor is None
        predictor = self._load()
        loaded_at = time.perf_counter()
        import torch
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[height//4:3*height//4, width//4:3*width//4] = (160, 110, 70)
        image_predictor = SAM2ImagePredictor(predictor)
        try:
            with torch.inference_mode():
                image_predictor.set_image(rgb)
                # CUDA work is asynchronous; synchronize for useful phase timings.
                if self.device == "cuda":
                    torch.cuda.synchronize()
                encoded_at = time.perf_counter()
                masks, scores, _ = image_predictor.predict(
                    point_coords=np.asarray([[width/2, height/2]], dtype=np.float32),
                    point_labels=np.asarray([1], dtype=np.int32),
                    multimask_output=True, normalize_coords=True)
                if self.device == "cuda":
                    torch.cuda.synchronize()
                if masks.shape != (3, height, width) or not np.all(np.isfinite(scores)):
                    raise RuntimeError("SAM warmup returned invalid mask dimensions or scores")
                finished = time.perf_counter()
        finally:
            image_predictor.reset_predictor()
        return {"seconds": finished-started, "device": self.device,
                "width": width, "height": height,
                "timing_ms": {"model_load": (loaded_at-started)*1000 if first_load else 0.,
                              "encoder": (encoded_at-loaded_at)*1000,
                              "decoder": (finished-encoded_at)*1000}}

    def preview(self, rgb, prompts, key):
        import numpy as np
        started = time.perf_counter()
        first_load = self._predictor is None
        predictor = self._load()
        loaded_at = time.perf_counter()
        import torch
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        hit = key in self.features
        with torch.inference_mode():
            if hit:
                image_predictor = self.features.pop(key)
            else:
                image_predictor = SAM2ImagePredictor(predictor)
                image_predictor.set_image(rgb)
            encoded_at = time.perf_counter()
            self.features[key] = image_predictor
            while len(self.features) > 2:
                self.features.popitem(last=False)
            masks, scores, _ = image_predictor.predict(
                point_coords=np.asarray([[p["x"], p["y"]] for p in prompts], dtype=np.float32),
                point_labels=np.asarray([p["label"] for p in prompts], dtype=np.int32),
                multimask_output=True, normalize_coords=True)
            mask = np.asarray(masks[int(np.argmax(scores))] > 0, dtype=np.uint8)
        finished = time.perf_counter()
        return mask, {"seconds": finished - started, "cache_hit": hit,
                      "timing_ms": {"model_load": self.model_load_seconds*1000 if first_load else 0.,
                                    "encoder": 0. if hit else (encoded_at-loaded_at)*1000,
                                    "decoder": (finished-encoded_at)*1000}}

    def segment(self, frames_dir, prompts, frame_count, progress_callback=None):
        import numpy as np
        import torch
        predictor = self._load()
        # Video state has its own features and is always rebuilt from the full prompts.
        self.features.clear()
        started = time.perf_counter()
        masks = {}
        with torch.inference_mode():
            state = predictor.init_state(str(frames_dir), offload_video_to_cpu=True, offload_state_to_cpu=True)
            try:
                for idx in sorted(prompts):
                    points = prompts[idx]
                    predictor.add_new_points_or_box(state, frame_idx=idx, obj_id=1,
                        points=np.asarray([[p["x"], p["y"]] for p in points], dtype=np.float32),
                        labels=np.asarray([p["label"] for p in points], dtype=np.int32),
                        normalize_coords=True, clear_old_points=True)
                # Official SAM starts at the earliest conditioning frame, not frame
                # zero. Seed ALL prompt frames first so both passes see every
                # correction. The reverse pass includes the anchor and stops at 0.
                anchor = min(prompts)
                passes = [(False, frame_count)]
                if anchor > 0:
                    passes.append((True, anchor))
                for reverse, distance in passes:
                    for idx, obj_ids, logits in predictor.propagate_in_video(
                            state, start_frame_idx=anchor,
                            max_frame_num_to_track=distance, reverse=reverse):
                        idx = int(idx)
                        if not 0 <= idx < frame_count:
                            raise RuntimeError("Official SAM2 propagation returned an out-of-range frame")
                        # Keep the forward anchor once; reverse yields it again.
                        # Never synthesize missing frames with empty masks.
                        if idx in masks:
                            continue
                        masks[idx] = (logits[list(obj_ids).index(1), 0] > 0).to(torch.uint8).cpu().numpy().copy()
                        if progress_callback:
                            progress_callback(len(masks), frame_count)
                if set(masks) != set(range(frame_count)):
                    raise RuntimeError("Official SAM2 propagation did not cover every frame")
            finally:
                predictor.reset_state(state)
                del state
        return masks, {"total_seconds": time.perf_counter()-started, "model_load_seconds": self.model_load_seconds,
                       "device": self.device, "threads": 4, "model_sha256": MODEL_SHA256, "source_commit": SOURCE_COMMIT}
