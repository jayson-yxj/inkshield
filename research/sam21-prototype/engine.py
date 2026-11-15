"""Official SAM 2.1 tiny CPU video inference, isolated from the production app.

Frames are original-resolution, contiguous 0-based numeric JPEGs. Points use
original image pixels. Each call rebuilds video state from the complete prompt
set, so corrections never accidentally reuse a previous request's memory.
"""
from __future__ import annotations

from pathlib import Path
import math
import hashlib
import threading
import time
from typing import Callable


class SegmentationCancelled(RuntimeError):
    """Cooperative cancellation; no partial masks are returned."""


class SamEngine:
    def __init__(self, checkpoint: str | Path | None = None, *, threads: int = 4):
        self.checkpoint = Path(checkpoint) if checkpoint else Path(__file__).parent / "models" / "sam2.1_hiera_tiny.pt"
        self.threads = threads
        self._predictor = None
        self._lock = threading.Lock()
        self.model_load_seconds = 0.0

    def _load(self):
        if self._predictor is None:
            started = time.perf_counter()
            # Pin the official artifact before deserializing it.
            expected = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
            digest = hashlib.sha256()
            with self.checkpoint.open("rb") as checkpoint_file:
                for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise RuntimeError("SAM2.1 tiny checkpoint SHA256 does not match official weights")
            import torch
            from sam2.build_sam import build_sam2_video_predictor
            torch.set_num_threads(self.threads)
            # No CUDA extension: hole filling specifically needs that extension.
            # Keep the official dynamic multimask/binarization postprocessing.
            self._predictor = build_sam2_video_predictor(
                "configs/sam2.1/sam2.1_hiera_t.yaml",
                str(self.checkpoint), device="cpu",
                hydra_overrides_extra=["++model.fill_hole_area=0"],
                vos_optimized=False,
            )
            # Upstream appends its defaults after user overrides; enforce this
            # CPU-only option explicitly without altering vendored source.
            self._predictor.fill_hole_area = 0
            self.model_load_seconds = time.perf_counter() - started
        return self._predictor

    def segment(
        self,
        frames_dir: str | Path,
        prompts: dict[int, list[dict]],
        frame_count: int,
        cancel_callback: Callable[[], bool] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[dict, dict]:
        """Return {frame: uint8 HxW mask (0/1)}, timing seconds.

        All prompt frames are registered as conditioning frames for object 1.
        Forward starts at the earliest prompt; reverse starts at the same anchor
        and covers preceding frames. Corrected prompt frames remain authoritative.
        Cancellation is checked between CPU inference steps (not inside torch).
        Progress reports unique completed frame count and total frame count.
        """
        import numpy as np
        from PIL import Image

        def cancelled():
            if cancel_callback is not None and cancel_callback():
                raise SegmentationCancelled("SAM2 video segmentation cancelled")

        cancelled()
        directory = Path(frames_dir).resolve()
        if type(frame_count) is not int or not 1 <= frame_count <= 150:
            raise ValueError("frame_count must be an integer from 1 through 150")
        jpgs = [p for p in directory.iterdir() if p.suffix.lower() in (".jpg", ".jpeg")]
        try:
            jpgs.sort(key=lambda p: int(p.stem))
            indices = [int(p.stem) for p in jpgs]
        except ValueError as exc:
            raise ValueError("SAM2 requires numeric JPEG filenames") from exc
        if indices != list(range(frame_count)):
            raise ValueError("JPEG frames must be exactly contiguous indices 0..frame_count-1")
        size = None
        for path in jpgs:
            cancelled()
            with Image.open(path) as image:
                if size is None:
                    size = image.size
                if image.size != size:
                    raise ValueError("All frames must have identical dimensions")
        width, height = size
        if width > 1280 or height > 720:
            raise ValueError("Frame dimensions exceed 1280x720 research limit")
        if not prompts:
            raise ValueError("At least one positive point is required")
        normalized = {}
        for key, clicks in prompts.items():
            if isinstance(key, bool) or not isinstance(key, (int, str)):
                raise ValueError("Prompt frame must be an integer")
            try:
                idx = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError("Prompt frame must be an integer") from exc
            if not 0 <= idx < frame_count or not clicks:
                raise ValueError("Prompt frame outside video or empty point list")
            points, labels = [], []
            for point in clicks:
                x, y, label = float(point["x"]), float(point["y"]), point["label"]
                if label not in (0, 1) or not math.isfinite(x) or not math.isfinite(y):
                    raise ValueError("Points require finite x/y and label 0 or 1")
                if not (0 <= x < width and 0 <= y < height):
                    raise ValueError("Point outside original frame bounds")
                points.append([x, y])
                labels.append(int(label))
            if 1 not in labels:
                raise ValueError("Every prompted frame requires at least one positive point; include the positive with negative corrections")
            normalized[idx] = (np.asarray(points, dtype=np.float32), np.asarray(labels, dtype=np.int32))
        if not any(1 in labels for _, labels in normalized.values()):
            raise ValueError("At least one positive point is required")

        with self._lock:
            cancelled()
            first_load = self._predictor is None
            predictor = self._load()
            import torch
            cancelled()
            started = time.perf_counter()
            masks = {}
            with torch.inference_mode():
                state = predictor.init_state(str(directory), offload_video_to_cpu=True, offload_state_to_cpu=True)
                loaded = time.perf_counter()
                try:
                    for idx in sorted(normalized):
                        cancelled()
                        points, labels = normalized[idx]
                        predictor.add_new_points_or_box(state, frame_idx=idx, obj_id=1,
                            points=points, labels=labels, normalize_coords=True, clear_old_points=True)
                    prompted = time.perf_counter()
                    anchor = min(normalized)
                    forward_seconds = 0.0
                    reverse_seconds = 0.0
                    for reverse in (False, True):
                        pass_started = time.perf_counter()
                        cancelled()
                        for idx, obj_ids, logits in predictor.propagate_in_video(
                            state, start_frame_idx=anchor, reverse=reverse,
                        ):
                            cancelled()
                            obj_index = list(obj_ids).index(1)
                            mask = (logits[obj_index, 0] > 0).to(torch.uint8).cpu().numpy().copy()
                            if mask.shape != (height, width):
                                raise RuntimeError("Official SAM2 mask dimensions differ from source frame")
                            masks[int(idx)] = mask
                            if progress_callback is not None:
                                progress_callback(len(masks), frame_count)
                        elapsed = time.perf_counter() - pass_started
                        if reverse:
                            reverse_seconds = elapsed
                        else:
                            forward_seconds = elapsed
                    cancelled()
                    if set(masks) != set(range(frame_count)):
                        raise RuntimeError("Official SAM2 propagation did not cover every frame")
                finally:
                    predictor.reset_state(state)
                    del state
            total = time.perf_counter() - started
            return masks, {
                "model_load_seconds": self.model_load_seconds if first_load else 0.0,
                "frame_loading_seconds": loaded - started,
                "prompt_seconds": prompted - loaded,
                "forward_seconds": forward_seconds,
                "reverse_seconds": reverse_seconds,
                "total_seconds": total,
                "seconds_per_frame": total / frame_count,
                "frame_count": frame_count,
                "anchor_frame": anchor,
                "prompt_frame_count": len(normalized),
                "threads": self.threads,
                "device": "cpu",
                "model": "sam2.1_hiera_tiny",
                "mask_values": "0/1",
            }
