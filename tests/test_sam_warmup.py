"""Startup device selection contracts; no real torch, CUDA, or model inference."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import sam_service


class ImmediateThread:
    def __init__(self, target, args=(), **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class SamWarmupTests(unittest.TestCase):
    def setUp(self):
        # Patch whole containers/locks, so tests cannot clear another user's model
        # cache or leave production startup state changed in this interpreter.
        self.state = {"state": "pending", "device": None, "seconds": 0.,
                      "error": None, "fallback_reason": None}
        self.engines = {}
        self.lock = threading.Lock()
        for name, value in (("WARMUP_STATE", self.state), ("ENGINES", self.engines),
                            ("SAM_LOCK", self.lock), ("WARMUP_LOCK", threading.Lock()),
                            ("threading", SimpleNamespace(Thread=ImmediateThread))):
            patcher = patch.object(sam_service, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def caps(self, cuda=False, available=True):
        return {"available": available, "reason": None if available else "assets unavailable",
                "devices": [{"id": "cpu", "available": True},
                            {"id": "cuda", "available": cuda}]}

    def assert_locks_released(self):
        for lock in (sam_service.SAM_LOCK, sam_service.WARMUP_LOCK):
            acquired = lock.acquire(blocking=False)
            self.assertTrue(acquired)
            if acquired:
                lock.release()

    def test_gpu_success_keeps_shared_warmed_instance_and_starts_only_once(self):
        gpu = Mock()
        gpu.warmup.side_effect = lambda: self.assertTrue(self.lock.locked())
        with patch('sam_engine.capabilities', return_value=self.caps(cuda=True)), \
             patch('sam_engine.SamEngine', return_value=gpu) as constructor:
            sam_service.start_warmup()
            state = sam_service.warmup_status()
            self.assertEqual(state['state'], 'ready')
            self.assertEqual(state['device'], 'cuda')
            self.assertIsNone(state['error'])
            self.assertIsNone(state['fallback_reason'])
            self.assertGreaterEqual(state['seconds'], 0.)
            self.assertIs(sam_service.engine('cuda'), gpu)
            self.assertEqual(sam_service.ENGINES, {'cuda': gpu})
            sam_service.start_warmup()
            constructor.assert_called_once_with('cuda')
            gpu.warmup.assert_called_once_with()
        self.assert_locks_released()

    def test_gpu_failure_falls_back_to_clean_cpu_instance(self):
        gpu, cpu = Mock(), Mock()
        gpu.warmup.side_effect = RuntimeError('CUDA out of memory')
        def create(device):
            # The failed CUDA instance must be gone before constructing CPU.
            if device == 'cpu':
                self.assertNotIn('cuda', sam_service.ENGINES)
            return gpu if device == 'cuda' else cpu
        with patch('sam_engine.capabilities', return_value=self.caps(cuda=True)), \
             patch('sam_engine.SamEngine', side_effect=create) as constructor:
            sam_service.start_warmup()
            state = sam_service.warmup_status()
            self.assertEqual(state['state'], 'ready')
            self.assertEqual(state['device'], 'cpu')
            self.assertIn('CUDA out of memory', state['fallback_reason'])
            self.assertIsNone(state['error'])
            self.assertEqual([c.args[0] for c in constructor.call_args_list], ['cuda', 'cpu'])
            self.assertIs(sam_service.engine('cpu'), cpu)
            self.assertEqual(sam_service.ENGINES, {'cpu': cpu})
            gpu.warmup.assert_called_once_with()
            cpu.warmup.assert_called_once_with()
        self.assert_locks_released()

    def test_no_gpu_warms_cpu_directly_and_status_is_a_copy(self):
        cpu = Mock()
        with patch('sam_engine.capabilities', return_value=self.caps()), \
             patch('sam_engine.SamEngine', return_value=cpu) as constructor:
            sam_service.start_warmup()
            constructor.assert_called_once_with('cpu')
            cpu.warmup.assert_called_once_with()
        state = sam_service.warmup_status()
        self.assertEqual((state['state'], state['device']), ('ready', 'cpu'))
        self.assertIn('CPU', state['fallback_reason'])
        state['state'] = 'corrupted'
        self.assertEqual(sam_service.warmup_status()['state'], 'ready')
        self.assert_locks_released()

    def test_cuda_probe_failure_preserves_reason_and_warms_cpu(self):
        caps = self.caps()
        caps['devices'][1]['reason'] = 'CUDA device probe failed: driver unavailable'
        cpu = Mock()
        with patch('sam_engine.capabilities', return_value=caps), \
             patch('sam_engine.SamEngine', return_value=cpu) as constructor:
            sam_service.start_warmup()
            constructor.assert_called_once_with('cpu')
            cpu.warmup.assert_called_once_with()
        state = sam_service.warmup_status()
        self.assertEqual((state['state'], state['device']), ('ready', 'cpu'))
        self.assertIn(caps['devices'][1]['reason'], state['fallback_reason'])
        self.assertIsNone(state['error'])
        self.assertEqual(sam_service.ENGINES, {'cpu': cpu})
        self.assert_locks_released()

    def test_failed_warmup_releases_locks_and_clears_failed_shared_instance(self):
        for cuda in (False, True):
            with self.subTest(cuda=cuda):
                self.state.update(state='pending', device=None, error=None, fallback_reason=None)
                broken = Mock()
                broken.warmup.side_effect = RuntimeError('inference failed')
                with patch('sam_engine.capabilities', return_value=self.caps(cuda=cuda)), \
                     patch('sam_engine.SamEngine', return_value=broken):
                    sam_service.start_warmup()
                self.assertEqual(self.state['state'], 'error')
                self.assertIn('inference failed', self.state['error'])
                self.assertEqual(sam_service.ENGINES, {})
                self.assert_locks_released()
                fresh = Mock()
                with patch('sam_engine.SamEngine', return_value=fresh) as constructor:
                    self.assertIs(sam_service.engine('cpu'), fresh)
                    constructor.assert_called_once_with('cpu')
                self.engines.clear()

    def test_unavailable_assets_fail_without_constructing_engine(self):
        with patch('sam_engine.capabilities', return_value=self.caps(available=False)), \
             patch('sam_engine.SamEngine') as constructor:
            sam_service.start_warmup()
            constructor.assert_not_called()
        self.assertEqual(self.state['state'], 'error')
        self.assertEqual(self.state['error'], 'assets unavailable')
        self.assertEqual(self.engines, {})
        self.assert_locks_released()

    def test_thread_start_failure_releases_state_lock(self):
        thread = Mock()
        thread.start.side_effect = RuntimeError('cannot start thread')
        with patch.object(sam_service, 'threading', SimpleNamespace(Thread=Mock(return_value=thread))):
            sam_service.start_warmup()
        self.assertEqual(self.state['state'], 'error')
        self.assertIn('cannot start thread', self.state['error'])
        self.assert_locks_released()


if __name__ == '__main__':
    unittest.main()
