# HyperLPR3 detector-only source and limitations

Acquired 2026-11-03. Used locally without installing the HyperLPR3 package or OCR dependencies.

## Model artifact

- File: `models/y5fu_320x_sim.onnx`
- Bytes: **2,343,161** (2.23 MiB); SHA256: **2a985dc63a5cc947ec36d18503d6fc0fd54525b9dba17f2fe29a71e86b44456d**.
- Download source (third-party redistribution, not original author): <https://gitee.com/dreamlu/mica-ai/raw/master/model-tools/plate/models/y5fu_320x_sim.onnx>, following its normal HTTPS redirect to `raw.giteeusercontent.com`. TLS certificate verification remained enabled.
- Source discovery/documentation: <https://www.dreamlu.net/mica-ai/core/plate/> (model-tools/plate/models).
- The official HyperLPR3 0.1.3 settings name this same model filename. Its original model archive URL is `http://hyperlpr.tunm.top/raw/20230229.zip`. HTTPS to the official host failed `CERTIFICATE_VERIFY_FAILED: EE certificate key too weak`; did not disable TLS verification or downgrade to HTTP. Original-author hash equivalence is **not established**. Prior secondary model-size reports do not match this downloaded artifact; do not represent them as this artifact's actual size.

## Original code evidence and license boundary

- Project: <https://github.com/szad670401/HyperLPR>.
- Official PyPI metadata: <https://pypi.org/pypi/hyperlpr3/json>.
- Inspected `hyperlpr3-0.1.3-py3-none-any.whl` in `research/hyperlpr3/`; wheel SHA256 **9ff3f94c9897c28f4d1b9a8d7c3996321076b3c20670d538c4c4b706360e4008**, checked against PyPI's published digest.
- Wheel metadata declares **Apache License 2.0** and an Apache classifier. Wheel contains no LICENSE/NOTICE file, no models and no sample images. Thus this is a verified **package metadata declaration**, not an independently verified full license grant for this redistributed detector weight.
- Geometry and decoder were inspected in `hyperlpr3/inference/multitask_detect.py`; no HyperLPR3 import, installation, OCR classifier, or recognition model is used at runtime.
- Standalone weight license, training data rights, original training/backbone dependencies, third-party redistribution rights and commercial clearance remain **unverified**. Do not infer that the package's Apache metadata or the mirror's own project license automatically clears all model rights. Retain this distinction before redistribution or commercial deployment.

## Verified executable contract

- ONNX Runtime loads the downloaded bytes successfully with CPUExecutionProvider.
- Input name `input`: float32 `[1,3,320,320]`; output `output`: float32 `[1,6300,15]`.
- Upstream preprocessing: preserve aspect ratio with `r=min(320/h,320/w)`; resized sizes use integer truncation, centered **black** padding; BGR→RGB, NCHW, divide by 255.
- Output columns: center x/y, width/height, objectness, eight **model-predicted** corner coordinates, two plate-layout class probabilities. No OCR characters are returned by this model.
- Module score: objectness × maximum layout-class probability; applies both objectness prefilter and final fused-score threshold. The final fused-score filter is intentional (upstream helper only prefilters objectness).
- Class-agnostic bbox IoU NMS 0.5, inverse letterbox, clipping to original frame; public detection is `(x0,y0,x1,y1,score,21)`. Both internal layout classes map to application plate class 21.
- `detect_with_corners` optionally retains the predicted points in original model order; first-version masking uses rectangles only. They are not bbox-derived points, but point accuracy/order semantics have not received independent visual validation.
- Session construction uses `Path(path).read_bytes()` for Unicode paths, CPU provider, four intra-op threads and one inter-op thread. No per-frame state is shared.

## Tests and acceptance limits

`research/hyperlpr3/test_plate_detector.py` checks RGB normalization/black padding, inverse geometry, fused-score filtering, NMS duplicate removal, finite-value filtering, predicted-corner preservation, boundary clipping and invalid inputs. `research/hyperlpr3/benchmark.json` records real-model synthetic black-frame CPU timing. Upstream parity was additionally checked: four exact preprocessing cases (99×201, 721×1280, 1280×721, 320×320) and eight synthetic confidence/geometry rows match the original helpers (outside intentional final-score filtering/clipping changes).

Actual upstream quicktest external sample, downloaded by the parent agent from <https://koss.iyong.com/swift/v1/iyong_public/iyong_2596631159095872/image/20190221/1550713902741045679.jpg>: SHA256 `421515779c86e186cdd91e158d90a4e0d6d373423b4a5c2749b2bfd4879449ac`, 640×478. At threshold 0.3 the real model returns one detection: `(266.073,344.545,436.707,406.500,0.921548,21)`. CPU4, five warmups plus 30 repetitions: median **11.11 ms**, p95 **12.12 ms**, including preprocessing and decoding. Full predicted corners/timing in `research/hyperlpr3/positive-test.json`; annotated test image in the same directory. Standalone sample-image license is unverified: **local test only, no redistribution-rights claim**. The implementing agent could not visually inspect the annotated image (runtime model lacks image input), so numeric detection is not itself a visual-alignment verification.

Black 1280×720 input: zero detections; same repetition protocol median **11.06 ms**, p95 **13.58 ms**. Measurements are machine/run-specific single-frame calls, not sustained video throughput. These are module/contract and one-positive-sample checks, **not** representative Chinese-plate quality, video throughput, commercial-license or privacy-coverage acceptance.
