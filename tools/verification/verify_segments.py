"""Real encoded-video segment regression; fake detectors avoid model inference.

Run: .venv/Scripts/python.exe verify_segments.py
API metadata/range errors are synchronous 422. Decode failures after worker start
remain job state=error and never publish a ready cache.
"""

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient
from inkshield import server


class FakeDetector:
    def __init__(self, plate=False):
        self.pixels = []
        self.plate = plate
        self.session = self

    def get_providers(self):
        return ["fake"]

    def detect(self, frame, targets=None, threshold=None):
        self.pixels.append(float(frame[24, 48, 0]))
        if self.plate:
            return []
        assert targets == server.HUMAN_TARGETS
        return [(4, 4, 16, 16, .9, 7)]


def decoded(path):
    cap = cv2.VideoCapture(str(path))
    result = []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                return result
            result.append(frame)
    finally:
        cap.release()


class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.mp4"
        writer = cv2.VideoWriter(str(self.source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
        self.assertTrue(writer.isOpened())
        for i in range(12):
            writer.write(np.full((48, 64, 3), 20 + i * 16, np.uint8))
        writer.release()
        self.original = decoded(self.source)
        self.assertEqual(len(self.original), 12)
        self.head, self.plate = FakeDetector(), FakeDetector(True)
        self.patches = [patch.object(server, "RUNTIME", self.root),
                        patch.object(server, "get_detector", return_value=self.head),
                        patch.object(server, "get_plate_detector", return_value=self.plate),
                        patch.object(server, "ACTIVE_JOBS", threading.BoundedSemaphore(2))]
        for item in self.patches:
            item.start()
        self.client = TestClient(server.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def analyze(self, name, start=0, end=None):
        server.new_job(name, "analysis")
        return server.analyze_video(name, self.source, start_frame=start, end_frame=end)

    def test_segment_pixels_preview_export_and_cache(self):
        analysis = self.analyze("segment", 3, 7)
        self.assertEqual(analysis.start_frame, 3)
        self.assertEqual(len(analysis.boxes), 4)
        expected = [float(frame[24, 48, 0]) for frame in self.original[3:7]]
        self.assertEqual(self.head.pixels, expected)
        self.assertEqual(self.plate.pixels, expected)
        state = server.status("segment")
        self.assertEqual((state["start_frame"], state["end_frame"], state["frames"]), (3, 7, 4))
        cache = json.loads((self.root / "segment" / "detections.json").read_text())
        self.assertEqual((cache["start_frame"], cache["end_frame"]), (3, 7))
        self.assertFalse((self.source.parent / "detections.json").exists())
        payload = self.client.get("/api/playback/segment").json()
        self.assertEqual((payload["start_frame"], payload["end_frame"], payload["frames"]), (3, 7, 4))
        for local in (0, 3):
            response = self.client.get(f"/api/preview/segment?frame={local}&style=black")
            self.assertEqual(response.status_code, 200)
            image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
            self.assertLess(abs(float(image[24, 48, 0]) - expected[local]), 4)
        self.assertEqual(self.client.get("/api/preview/segment?frame=4").status_code, 422)
        server.new_job("export", "export")
        out = self.root / "export.mp4"
        server.export_video("export", analysis, out, ("head",), 68, "black")
        output = decoded(out)
        self.assertEqual(len(output), 4)
        for index, frame in enumerate(output):
            self.assertLess(abs(float(frame[24, 48, 0]) - expected[index]), 6)
            self.assertLess(float(frame[10, 10].mean()), 8)
        self.assertEqual(server.status("export")["inference_ms"], 0)
        self.assertEqual(self.head.pixels, expected)
        self.assertEqual(self.plate.pixels, expected)

    def test_full_video_and_open_end_compatibility(self):
        legacy_lock = threading.Lock()
        legacy = server.Analysis(self.source, (), 64, 48, 10, legacy_lock)
        self.assertEqual(legacy.start_frame, 0)
        self.assertIs(legacy.decode_lock, legacy_lock)
        full = self.analyze("full")
        self.assertEqual(len(full.boxes), 12)
        tail = self.analyze("tail", 10)
        self.assertEqual(len(tail.boxes), 2)
        self.assertEqual(server.status("tail")["end_frame"], 12)

    def test_media_api_no_models_and_range_validation_before_worker(self):
        with patch.object(server, "get_detector", side_effect=AssertionError("model load")), patch.object(server, "get_plate_detector", side_effect=AssertionError("model load")):
            response = self.client.post("/api/media", files={"video": ("video.mp4", self.source.read_bytes(), "video/mp4")})
        self.assertEqual(response.status_code, 200, response.text)
        media = response.json()
        self.assertEqual((media["frames"], media["width"], media["height"]), (12, 64, 48))
        self.assertEqual(self.head.pixels, [])
        with patch.object(server, "start_worker") as worker:
            for data in ({"start_frame": -1}, {"start_frame": "bad"}, {"start_frame": 3, "end_frame": 3},
                         {"start_frame": 5, "end_frame": 4}, {"end_frame": 13}, {"start_frame": 12}, {"end_frame": 0}):
                result = self.client.post("/api/analyze", data={"media_id": media["media_id"], **data})
                self.assertEqual(result.status_code, 422, result.text)
            worker.assert_not_called()
        self.assertEqual(self.client.post("/api/analyze").status_code, 422)
        self.assertEqual(self.client.post("/api/media", files={"video": ("empty.mp4", b"", "video/mp4")}).status_code, 422)
        self.assertEqual(self.client.post("/api/analyze", data={"media_id": "missing"}).status_code, 404)
        # Execute workers inline, releasing their acquired semaphore as production does.
        with patch.object(server, "start_worker", side_effect=lambda operation, *args: server.run_worker(operation, *args)):
            first = self.client.post("/api/analyze", data={"media_id": media["media_id"], "start_frame": 2, "end_frame": 5})
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual((first.json()["start_frame"], first.json()["end_frame"], first.json()["frames"]), (2, 5, 3))
            second = self.client.post("/api/analyze", data={"media_id": media["media_id"], "start_frame": 8})
            self.assertEqual(second.status_code, 200, second.text)
            direct = self.client.post("/api/analyze", files={"video": ("video.mp4", self.source.read_bytes(), "video/mp4")})
            self.assertEqual(direct.status_code, 200, direct.text)
            self.assertEqual(direct.json()["frames"], 12)
        for result in (first, second, direct):
            info = result.json()
            self.assertEqual(server.status(info["job_id"])["state"], "ready")
            self.assertTrue((self.root / info["job_id"] / "detections.json").is_file())
        self.assertTrue(server.MEDIA[media["media_id"]]["input_path"].is_file())

    def test_bad_metadata_and_truncated_decode_do_not_publish(self):
        class InvalidFPS:
            def isOpened(self):
                return True
            def get(self, key):
                return float("nan")
            def release(self):
                pass
        with patch.object(server.cv2, "VideoCapture", return_value=InvalidFPS()):
            with self.assertRaisesRegex(RuntimeError, "帧率"):
                server.inspect_video(self.source)
        with patch.object(server, "video_metadata", side_effect=lambda cap: (10, 14, 64, 48)):
            server.new_job("truncated", "analysis")
            with self.assertRaisesRegex(RuntimeError, "提前停止解码"):
                server.analyze_video("truncated", self.source, start_frame=10, end_frame=14)
        self.assertNotIn("truncated", server.ANALYSES)
        self.assertFalse((self.root / "truncated" / "detections.json").exists())
        # Full-video legacy decoding must not silently truncate to an underreported count.
        with patch.object(server, "video_metadata", side_effect=lambda cap: (10, 10, 64, 48)):
            analysis = self.analyze("underreported")
        self.assertEqual(len(analysis.boxes), 12)
        self.assertEqual(server.status("underreported")["end_frame"], 12)

    def test_parallel_failure_drains_worker_without_cache(self):
        for failed in ('human', 'plate'):
            entered, finished = threading.Event(), threading.Event()
            def plate(frame, threshold):
                entered.set()
                if failed == 'plate':
                    raise RuntimeError('plate failed')
                # Wait briefly for the human exception to unwind before finishing.
                finished.wait(.03)
                finished.set()
                return []
            def human(frame, targets, threshold):
                self.assertTrue(entered.wait(1))
                if failed == 'human':
                    raise RuntimeError('human failed')
                return []
            name = 'failure-' + failed
            with patch.object(server, 'PARALLEL_MODELS', True), patch.object(self.head, 'detect', side_effect=human), patch.object(self.plate, 'detect', side_effect=plate):
                with self.assertRaisesRegex(RuntimeError, failed + ' failed'):
                    self.analyze(name, 0, 1)
            if failed == 'human':
                self.assertTrue(finished.is_set())
            self.assertNotIn(name, server.ANALYSES)
            self.assertFalse((self.root / name / 'detections.json').exists())
            self.assertTrue(server.PROCESS_LOCK.acquire(blocking=False))
            server.PROCESS_LOCK.release()

    def test_health_does_not_infer(self):
        response = self.client.get("/api/health")
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["threshold"], .5)
        self.assertEqual(self.head.pixels, [])
        self.assertEqual(self.plate.pixels, [])
        self.assertEqual(server.app.version, "0.10.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
