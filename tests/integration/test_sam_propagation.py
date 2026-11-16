"""Direction-aware official SAM video contracts, without loading torch/assets."""
import contextlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from inkshield.sam_engine import SamEngine


class Tensor:
    def __init__(self, array):
        self.array = np.asarray(array)

    def __getitem__(self, key):
        return Tensor(self.array[key])

    def __gt__(self, value):
        return Tensor(self.array > value)

    def to(self, dtype):
        return Tensor(self.array.astype(dtype))

    def cpu(self):
        return self

    def numpy(self):
        return self.array


class DirectionalPredictor:
    """Mirror vendor's inclusive ranges and preserved conditioning outputs.

    This deliberately never yields frames before start in a forward pass, unlike
    a mock that always emits the full video and hides a missing reverse pass.
    """
    def __init__(self, count, missing=(), fail_reverse=False, outside=False):
        self.count = count
        self.missing = set(missing)
        self.fail_reverse = fail_reverse
        self.outside = outside
        self.calls = []
        self.added = []
        self.reset = False
        self.buffer = np.empty((2, 1, 3, 4), np.float32)

    def init_state(self, path, **kwargs):
        self.state = {}
        return self.state

    def add_new_points_or_box(self, state, frame_idx, obj_id, points, labels, **kwargs):
        assert state is self.state and obj_id == 1
        self.added.append((frame_idx, points.copy(), labels.copy()))

    def propagate_in_video(self, state, start_frame_idx=None,
                           max_frame_num_to_track=None, reverse=False):
        assert state is self.state
        self.calls.append((start_frame_idx, max_frame_num_to_track, reverse,
                           tuple(frame for frame, _, _ in self.added)))
        if reverse and self.fail_reverse:
            raise RuntimeError('reverse inference failed')
        if self.outside:
            yield self.count, [9, 1], Tensor(self.buffer)
            return
        start = start_frame_idx
        distance = self.count if max_frame_num_to_track is None else max_frame_num_to_track
        order = (range(start, max(start-distance, 0)-1, -1) if start > 0 else []) if reverse else range(start, min(start+distance, self.count-1)+1)
        for idx in order:
            if idx in self.missing:
                continue
            self.buffer.fill(-1)
            # A real empty result remains empty. A different object is always full.
            self.buffer[0].fill(1)
            if idx != 1:
                self.buffer[1, 0, idx % 3, idx % 4] = 1
            yield idx, [9, 1], Tensor(self.buffer)

    def reset_state(self, state):
        assert state is self.state
        self.reset = True


class SamPropagationTests(unittest.TestCase):
    def run_segment(self, predictor, anchors):
        engine = SamEngine('cuda')
        engine._predictor = predictor
        engine.features['old-preview'] = object()
        progress = []
        torch = SimpleNamespace(inference_mode=contextlib.nullcontext, uint8=np.uint8)
        prompts = {idx: [{'x':idx + .5, 'y':1., 'label':1},
                         {'x':0., 'y':0., 'label':0}] for idx in anchors}
        with patch.dict(sys.modules, {'torch':torch}):
            masks, timing = engine.segment('isolated-frames', prompts, predictor.count,
                                           lambda done,total:progress.append((done,total)))
        self.assertEqual(engine.features, {})
        self.assertTrue(predictor.reset)
        self.assertEqual(set(masks), set(range(predictor.count)))
        self.assertEqual(progress, [(i,predictor.count) for i in range(1,predictor.count+1)])
        self.assertEqual(timing['device'], 'cuda')
        for idx, mask in masks.items():
            expected = np.zeros((3,4), np.uint8)
            if idx != 1:
                expected[idx % 3, idx % 4] = 1
            np.testing.assert_array_equal(mask, expected)
        # Predictor reuses its output buffer; stored masks must own their data.
        predictor.buffer.fill(99)
        self.assertFalse(np.any(masks[1]))
        return predictor

    def test_middle_anchor_tracks_both_boundaries_and_real_empty_frame(self):
        predictor = self.run_segment(DirectionalPredictor(7), [3])
        self.assertEqual(predictor.calls, [(3,7,False,(3,)), (3,3,True,(3,))])

    def test_first_and_last_anchor_follow_official_boundary_semantics(self):
        for anchor in (0,6):
            with self.subTest(anchor=anchor):
                predictor = self.run_segment(DirectionalPredictor(7), [anchor])
                self.assertEqual(len(predictor.calls), 1 if anchor == 0 else 2)

    def test_all_unsorted_prompt_frames_are_seeded_before_either_pass(self):
        predictor = self.run_segment(DirectionalPredictor(7), [5,2,4])
        self.assertEqual(predictor.calls, [(2,7,False,(2,4,5)), (2,2,True,(2,4,5))])
        for idx, points, labels in predictor.added:
            np.testing.assert_array_equal(points, [[idx+.5,1.],[0.,0.]])
            np.testing.assert_array_equal(labels, [1,0])

    def test_missing_frame_fails_instead_of_filling_empty_mask(self):
        predictor = DirectionalPredictor(7, missing=[0])
        with self.assertRaisesRegex(RuntimeError, 'did not cover every frame'):
            self.run_segment(predictor, [3])
        self.assertTrue(predictor.reset)

    def test_reverse_failure_and_out_of_range_output_reset_state(self):
        for predictor, error in ((DirectionalPredictor(7, fail_reverse=True), 'reverse inference failed'),
                                 (DirectionalPredictor(7, outside=True), 'out-of-range frame')):
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                self.run_segment(predictor, [3])
            self.assertTrue(predictor.reset)


if __name__ == '__main__':
    unittest.main()
