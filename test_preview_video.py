"""Inference-free HTTP and real H264/AAC continuous preview acceptance."""
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import av
import cv2
import imageio_ffmpeg
import numpy as np
from fastapi.testclient import TestClient

import server
import preview_video


class PreviewVideoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = patch.object(server, 'RUNTIME', self.root)
        self.runtime.start()
        self.addCleanup(self.runtime.stop)
        self.jobs = dict(server.JOBS)
        self.analyses = dict(server.ANALYSES)
        self.cache = dict(server.CUSTOM_PLAYBACK_CACHE)
        server.CUSTOM_PLAYBACK_CACHE.clear()
        self.addCleanup(self.restore)
        self.client = TestClient(server.app)
        self.addCleanup(self.client.close)

    def restore(self):
        server.JOBS.clear(); server.JOBS.update(self.jobs)
        server.ANALYSES.clear(); server.ANALYSES.update(self.analyses)
        server.CUSTOM_PLAYBACK_CACHE.clear(); server.CUSTOM_PLAYBACK_CACHE.update(self.cache)

    def fixture(self, audio=True, odd=True):
        source = self.root / ('audio.mp4' if audio else 'silent.mp4')
        size = '81x63' if odd else '80x64'
        cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', f'color=c=white:s={size}:r=12:d=1,format=yuv444p']
        if audio:
            cmd += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=1', '-c:a', 'aac']
        cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv444p', str(source)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        width, height = (81, 63) if odd else (80, 64)
        masks = []
        # First frame is a legitimate all-empty mask; others protect the center.
        for index in range(6):
            mask = np.zeros((height, width), np.uint8)
            if index:
                mask[20:40, 25:55] = 255
            mask.flags.writeable = False
            masks.append(mask)
        analysis = server.Analysis(source, ((),) * 6, width, height, 12,
                                   start_frame=3, face_ids=((),) * 6, custom_masks=tuple(masks))
        server.new_job('custom', 'sam-analysis', state='ready')
        server.ANALYSES['custom'] = analysis
        return analysis

    def wait(self, job_id):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            job = self.client.get('/api/status/' + job_id).json()
            if job['state'] in ('done', 'error'):
                return job
            threading.Event().wait(.02)
        self.fail('preview worker timed out')

    def post(self, style='black', strength=68):
        return self.client.post('/api/custom-playback/custom', data={'style': style, 'strength': strength})

    def test_actual_audio_odd_dimensions_range_and_reuse(self):
        analysis = self.fixture()
        with patch.object(server, 'get_detector', side_effect=AssertionError('no inference')), \
             patch.object(server, 'get_plate_detector', side_effect=AssertionError('no inference')):
            result = self.post()
            self.assertEqual(result.status_code, 200, result.text)
            data = result.json()
            reused = self.post().json()
            self.assertEqual(reused['job_id'], data['job_id'])
            self.assertTrue(reused['reused'])
            job = self.wait(data['job_id'])
            self.assertEqual(job['state'], 'done', job)
        self.assertTrue(job['audio_present'])
        self.assertEqual((job['width'], job['height']), (82, 64))
        self.assertEqual((job['source_width'], job['source_height']), (81, 63))
        self.assertEqual(job['duration'], .5)
        full = self.client.get(job['url'])
        self.assertEqual(full.status_code, 200)
        self.assertNotIn('attachment', full.headers.get('content-disposition', ''))
        ranged = self.client.get(job['url'], headers={'Range': 'bytes=0-99'})
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged.content, full.content[:100])
        self.assertEqual(ranged.headers['accept-ranges'], 'bytes')
        raw = full.content
        self.assertLess(raw.index(b'moov'), raw.index(b'mdat'))
        output = self.root / data['job_id'] / 'playback.mp4'
        with av.open(str(output)) as container:
            self.assertEqual(container.streams.video[0].codec_context.name, 'h264')
            self.assertEqual(container.streams.audio[0].codec_context.name, 'aac')
            frames = list(container.decode(video=0))
            self.assertEqual(len(frames), 6)
            self.assertEqual(frames[0].pts, 0)
            first = frames[0].to_ndarray(format='bgr24')
            second = frames[1].to_ndarray(format='bgr24')
            self.assertGreater(first[25:35,30:50].mean(), 230)
            self.assertLess(second[25:35,30:50].mean(), 8)
        with av.open(str(output)) as container:
            audio_frames = list(container.decode(audio=0))
            self.assertGreater(sum(frame.samples for frame in audio_frames), 23000)
            values = np.concatenate([frame.to_ndarray().ravel() for frame in audio_frames])
            self.assertGreater(float(np.max(np.abs(values))), .01)
        self.assertFalse((output.parent / 'protected.mp4').exists())
        self.assertFalse((output.parent / 'video-only.mp4').exists())

    def test_settings_invalidation_and_silent_all_styles(self):
        self.fixture(audio=False, odd=False)
        previous = set()
        for style in server.MASK_STYLES:
            data = self.post(style).json()
            self.assertNotIn(data['job_id'], previous)
            previous.add(data['job_id'])
            job = self.wait(data['job_id'])
            self.assertEqual(job['state'], 'done', job)
            self.assertFalse(job['audio_present'])
        changed = self.post('black', 69).json()
        self.assertNotIn(changed['job_id'], previous)
        self.assertEqual(self.wait(changed['job_id'])['state'], 'done')

    def test_mask_validation_and_unknown_style(self):
        analysis = self.fixture(audio=False)
        for masks in ((), analysis.custom_masks[:-1], (np.zeros((1, 1), np.uint8),) * 6):
            server.ANALYSES['custom'] = replace(analysis, custom_masks=masks)
            self.assertEqual(self.post().status_code, 409)
        mutable = tuple(mask.copy() for mask in analysis.custom_masks)
        server.ANALYSES['custom'] = replace(analysis, custom_masks=mutable)
        self.assertEqual(self.post().status_code, 409)
        server.ANALYSES['custom'] = analysis
        self.assertEqual(self.post('invalid').status_code, 422)
        self.assertEqual(len(server.CUSTOM_PLAYBACK_CACHE), 0)

    def test_quota_launch_failure_and_worker_failure_release_slots(self):
        self.fixture(audio=False)
        with patch.object(server, 'start_worker', side_effect=RuntimeError('launch failure')):
            with self.assertRaisesRegex(RuntimeError, 'launch failure'):
                self.post()
        self.assertEqual(len(server.CUSTOM_PLAYBACK_CACHE), 0)
        with patch.object(preview_video, 'transcode_browser_video', side_effect=RuntimeError('encode failure')):
            data = self.post().json()
            job = self.wait(data['job_id'])
            self.assertEqual(job['state'], 'error')
            self.assertIsNone(job['url'])
            self.assertEqual(self.client.get('/api/custom-playback-video/' + data['job_id']).status_code, 409)
            # Worker completes cleanup immediately after error publication.
            deadline = time.monotonic() + 2
            while server.CUSTOM_PLAYBACK_CACHE and time.monotonic() < deadline:
                threading.Event().wait(.01)
        self.assertEqual(len(server.CUSTOM_PLAYBACK_CACHE), 0)
        self.assertFalse((self.root / data['job_id'] / 'playback.mp4').exists())
        retry = self.post().json()
        self.assertNotEqual(retry['job_id'], data['job_id'])
        self.assertEqual(self.wait(retry['job_id'])['state'], 'done')
        acquired = [server.ACTIVE_JOBS.acquire(blocking=False) for _ in range(server.MAX_ACTIVE_JOBS)]
        self.assertTrue(all(acquired))
        self.assertEqual(self.post('blur').status_code, 429)
        for value in acquired:
            if value: server.ACTIVE_JOBS.release()
        with patch.object(preview_video, 'MAX_CACHED_PREVIEWS', 0):
            self.assertEqual(self.post('blur').status_code, 429)


if __name__ == '__main__':
    unittest.main(verbosity=2)
