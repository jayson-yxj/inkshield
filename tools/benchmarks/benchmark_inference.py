"""Read-only model benchmark: CPU ORT threads, production decode/filter, no quality changes.

Run from project root with .venv/Scripts/python.exe benchmark_inference.py.
Timings include preprocessing, session.run and postprocessing, but exclude video
read/decode, model construction, UI, exports and cache writes. Fixtures are small
regression samples, not a representative quality or sustained-throughput corpus.
"""
from __future__ import annotations

import sys as _tool_sys
from pathlib import Path as _ToolPath
_TOOL_ROOT = _ToolPath(__file__).resolve().parents[2]
for _tool_path in (_TOOL_ROOT / 'src', _TOOL_ROOT / 'tools/verification'):
    if str(_tool_path) not in _tool_sys.path:
        _tool_sys.path.insert(0, str(_tool_path))


import argparse
import gc
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from inkshield import server
from inkshield.plate_detector import PlateDetector

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frames():
    frames, provenance = [], []
    for relative, indices, origin in (
        ('runtime/mask-test-input.mp4', (0, 4), 'Existing human regression clip (576x1024), original user clip excerpt'),
        ('runtime/plate-real-input.mp4', (0,), 'Existing repeated upstream HyperLPR quicktest image, not a dynamic road clip'),
    ):
        path = ROOT / relative
        if not path.is_file():
            continue
        cap = cv2.VideoCapture(str(path))
        try:
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok:
                    continue
                frames.append(frame)
                provenance.append({'path': relative, 'frame_index': idx, 'width': frame.shape[1],
                                   'height': frame.shape[0], 'sha256_file': digest(path),
                                   'sha256_decoded_pixels': hashlib.sha256(frame.tobytes()).hexdigest(), 'origin': origin})
        finally:
            cap.release()
    if not frames:
        raise RuntimeError('No existing real benchmark fixture found')
    return frames, provenance


def make_detectors(threads, spinning=None, plate_threads=None):
    def session(path, thread_count):
        options = ort.SessionOptions()
        options.intra_op_num_threads = thread_count
        options.inter_op_num_threads = 1
        if spinning is not None:
            options.add_session_config_entry('session.intra_op.allow_spinning', str(spinning))
        return ort.InferenceSession(path.read_bytes(), sess_options=options, providers=['CPUExecutionProvider'])
    # Bypass production constructors only to set thread counts; production detect
    # methods and graph preprocessing/postprocessing remain exactly as implemented.
    human = object.__new__(server.HeadDetector)
    human.session = session(server.MODEL_PATH, threads)
    human.input = human.session.get_inputs()[0]
    human.output_name = human.session.get_outputs()[0].name
    plate = object.__new__(PlateDetector)
    plate.session = session(server.PLATE_MODEL_PATH, plate_threads or threads)
    plate.input_name = plate.session.get_inputs()[0].name
    plate.output_name = plate.session.get_outputs()[0].name
    return human, plate


def timed_plate(detector, frame):
    start = time.perf_counter()
    result = detector.detect(frame, threshold=.5)
    return result, (time.perf_counter()-start)*1000


def stats(values):
    return {'samples': len(values), 'median_ms': round(statistics.median(values), 3),
            'p95_ms': round(float(np.percentile(values, 95)), 3),
            'mean_ms': round(statistics.mean(values), 3), 'min_ms': round(min(values), 3)}


def compare(reference, candidate):
    """Class-constrained nearest-box matching, avoids incidental output row order."""
    if len(reference) != len(candidate):
        return {'consistent': False, 'reference_count': len(reference), 'candidate_count': len(candidate)}
    unmatched = list(candidate)
    max_pixels = max_score = 0.0
    for box in reference:
        candidates = [(max(abs(float(a)-float(b)) for a, b in zip(box[:4], other[:4])), j)
                      for j, other in enumerate(unmatched) if int(box[5]) == int(other[5])]
        if not candidates:
            return {'consistent': False, 'reason': 'different classes'}
        delta, idx = min(candidates)
        other = unmatched.pop(idx)
        max_pixels = max(max_pixels, delta)
        max_score = max(max_score, abs(float(box[4])-float(other[4])))
    return {'consistent': max_pixels <= .05 and max_score <= 1e-5,
            'count': len(reference), 'max_coordinate_delta_pixels': max_pixels,
            'max_confidence_delta': max_score}


def run(args):
    original_cv_threads = cv2.getNumThreads()
    if args.opencv_threads is not None:
        cv2.setNumThreads(args.opencv_threads)
    frames, provenance = load_frames()
    report = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'hardware': {'processor': platform.processor(), 'cpu_name': os.environ.get('INKSHIELD_BENCH_CPU_NAME', 'unavailable'),
                           'physical_cores': os.environ.get('INKSHIELD_BENCH_PHYSICAL_CORES', 'unavailable'),
                           'logical_cpus': os.cpu_count()},
              'versions': {'python': platform.python_version(), 'onnxruntime': ort.__version__, 'opencv': cv2.__version__, 'numpy': np.__version__,
                           'platform': platform.platform()},
              'opencv_threads': cv2.getNumThreads(), 'opencv_original_threads': original_cv_threads, 'providers': ort.get_available_providers(),
              'threshold': .5, 'warmup_rounds': args.warmup, 'repeat_rounds': args.repeats, 'allow_spinning': args.spinning,
              'scope': ('Concurrent human+plate' if args.parallel else 'Sequential human+plate') + ' production detect calls on already decoded frames; excludes decoding/loading/cache/export/UI',
              'limitations': 'Three fixture frames, including repeated upstream plate sample; no accuracy/privacy/real-time claim; host background load uncontrolled',
              'fixtures': provenance, 'models': {'human_sha256': digest(server.MODEL_PATH), 'plate_sha256': digest(server.PLATE_MODEL_PATH)},
              'results': []}
    outputs_by_threads = {}
    counts = sorted({min(t, os.cpu_count() or 1) for t in args.threads})
    for threads in counts:
        load_start = time.perf_counter()
        human, plate = make_detectors(threads, args.spinning, args.plate_threads)
        load_seconds = time.perf_counter()-load_start
        for _ in range(args.warmup):
            for frame in frames:
                human.detect(frame, server.HUMAN_TARGETS, threshold=.5)
                plate.detect(frame, threshold=.5)
        human_ms, plate_ms, total_ms, outputs = [], [], [], []
        executor = ThreadPoolExecutor(max_workers=1) if args.parallel else None
        per_frame = [[] for _ in frames]
        for rep in range(args.repeats):
            for idx, frame in enumerate(frames):
                start = time.perf_counter()
                if executor:
                    future = executor.submit(timed_plate, plate, frame)
                    h = human.detect(frame, server.HUMAN_TARGETS, threshold=.5)
                    mid = time.perf_counter()
                    p, measured_plate_ms = future.result()
                else:
                    h = human.detect(frame, server.HUMAN_TARGETS, threshold=.5)
                    mid = time.perf_counter()
                    p = plate.detect(frame, threshold=.5)
                end = time.perf_counter()
                human_ms.append((mid-start)*1000)
                plate_ms.append(measured_plate_ms if executor else (end-mid)*1000)
                total_ms.append((end-start)*1000)
                per_frame[idx].append((end-start)*1000)
                if rep == 0:
                    outputs.append({'human': h, 'plate': p})
        outputs_by_threads[threads] = outputs
        if executor:
            executor.shutdown()
        result = {'intra_op_threads_each_model': threads, 'plate_threads': args.plate_threads or threads, 'parallel': args.parallel, 'inter_op_threads': 1, 'load_seconds': round(load_seconds, 3),
                  'human': stats(human_ms), 'plate': stats(plate_ms), 'sequential_total': stats(total_ms),
                  'per_frame_total': [stats(v) for v in per_frame]}
        report['results'].append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        del human, plate
        gc.collect()
    baseline_threads = 4 if 4 in outputs_by_threads else counts[-1]
    for result in report['results']:
        result['vs_default_four_thread_outputs'] = [
            {kind: compare(reference[kind], candidate[kind]) for kind in ('human', 'plate')}
            for reference, candidate in zip(outputs_by_threads[baseline_threads], outputs_by_threads[result['intra_op_threads_each_model']])]
        result['outputs_consistent'] = all(x[kind]['consistent'] for x in result['vs_default_four_thread_outputs'] for kind in ('human', 'plate'))
    best = min(report['results'], key=lambda r: r['sequential_total']['median_ms'])
    baseline = next(r for r in report['results'] if r['intra_op_threads_each_model'] == baseline_threads)
    report['recommendation'] = {'fastest_measured_threads': best['intra_op_threads_each_model'],
                                'median_speedup_vs_4threads': round(baseline['sequential_total']['median_ms']/best['sequential_total']['median_ms'], 3),
                                'all_outputs_consistent': all(r['outputs_consistent'] for r in report['results']),
                                'interpretation': 'Short controlled fixture comparison only. Prefer configurable CPU thread count; repeat on representative longer clip before claiming sustained gains.'}
    destination = ROOT / args.output
    destination.parent.mkdir(exist_ok=True, parents=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('REPORT', destination, json.dumps(report['recommendation']), flush=True)


def confirmation(args):
    """ABBA confirmation, dispose sessions between blocks to avoid idle spin interference."""
    from types import SimpleNamespace
    records = []
    for idx, label in enumerate(('baseline', 'candidate', 'candidate', 'baseline')):
        parallel = label == 'candidate'
        block = SimpleNamespace(opencv_threads=None, spinning=0 if parallel else None,
                                threads=[8] if parallel else [4], plate_threads=2 if parallel else 4,
                                parallel=parallel, warmup=2, repeats=8,
                                output=f'runtime/inference-confirm-{idx}-{label}.json')
        run(block)
        records.append(json.loads((ROOT/block.output).read_text(encoding='utf-8')))
    # Model configurations must produce matching class counts/confidences/coordinates.
    frames, _ = load_frames()
    reference_models = make_detectors(4)
    reference = [[reference_models[0].detect(f, server.HUMAN_TARGETS, .5), reference_models[1].detect(f, .5)] for f in frames]
    del reference_models
    gc.collect()
    candidate_models = make_detectors(8, 0, 2)
    candidate = [[candidate_models[0].detect(f, server.HUMAN_TARGETS, .5), candidate_models[1].detect(f, .5)] for f in frames]
    consistency = [[compare(a,b) for a,b in zip(ref, cand)] for ref,cand in zip(reference,candidate)]
    old_ms = statistics.mean(records[i]['results'][0]['sequential_total']['median_ms'] for i in (0, 3))
    new_ms = statistics.mean(records[i]['results'][0]['sequential_total']['median_ms'] for i in (1, 2))
    output = {'block_order': ['baseline4default', 'candidate8plate2parallel0', 'candidate8plate2parallel0', 'baseline4default'],
              'blocks': records, 'cross_configuration_consistency': consistency,
              'all_consistent': all(x['consistent'] for row in consistency for x in row),
              'summary': {'baseline_mean_block_median_ms': old_ms, 'candidate_mean_block_median_ms': new_ms,
                          'latency_reduction_percent': (1-new_ms/old_ms)*100, 'throughput_ratio': old_ms/new_ms}}
    (ROOT/args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CONFIRMATION', ROOT/args.output, output['all_consistent'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=6)
    parser.add_argument('--warmup', type=int, default=2)
    parser.add_argument('--output', default='runtime/inference-baseline.json')
    parser.add_argument('--opencv-threads', type=int, default=None)
    parser.add_argument('--threads', type=int, nargs='+', default=[1, 2, 4, 8])
    parser.add_argument('--spinning', type=int, choices=[0, 1], default=None)
    parser.add_argument('--plate-threads', type=int, default=None)
    parser.add_argument('--parallel', action='store_true')
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1 or args.warmup < 0 or any(t < 1 for t in args.threads) or (args.plate_threads is not None and args.plate_threads < 1):
        parser.error('repeats and threads must be positive; warmup must be nonnegative')
    confirmation(args) if args.confirm else run(args)
