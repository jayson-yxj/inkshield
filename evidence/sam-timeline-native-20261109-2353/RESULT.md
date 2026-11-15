# Final frozen Windows WebView2 timeline acceptance

Passed 15 checks. Tested HTML SHA-256 and served HTML SHA-256 were both `8b4b30351babd4f1fbbe5c36e5f0823875a2b97d060e690951b5e4c1f40743d6`; the HTML was unchanged at cleanup.

| Case | Held duration | DOM pointer events | Distinct visible pixel hashes during held drag | renderTimeline calls | Held JPEG requests | Peak in-flight JPEG bodies | Aborted JPEG requests including final |
|---|---:|---:|---:|---:|---:|---:|---:|
| Automatic cached geometry | 1.506 s | 45 | 31 | 0 | 0 | 0 | 0 |
| Unanalysed raw | 1.520 s | 47 | 12 | 0 | 0 | 0 | 0 |
| Custom, encoded protected video already cached | 1.509 s | 44 | 10 | 0 | 10 | 1 | 0 |
| Custom, no encoded protected-video cache | 1.524 s | 49 | 12 | 0 | 11 | 1 | 0 |
| Raw to custom across segment boundary | 2.030 s | 65 | 16 | 4 | 7 | 1 | 0 |

All final global/local frames matched requested targets. Automatic final decodedSourceFrame was 140; raw source ended at 5.6 seconds (frame 140 at 25 FPS). Both custom cache states ended at local/global frame 65 with the matching samDisplayed stamp. The actual visible custom frame-65 PNG matched a fresh real backend frame-65 JPEG with RGB mean absolute pixel error 0.0. Custom visible center pixels were black. During the raw-to-custom crossing, sampled analysed-custom states all hid raw source and any visible media retained the protected black center; final custom frame 10 had the matching stamp.

The stale-frame click case passed browser-side SAM capability/warmup gates using controlled test state, then deliberately set samDisplayed to frame 64 while the slider displayed frame 65. The production viewer handler returned `正在定位本帧，画面完成后再点选。`; prompts did not change and no SAM preview request occurred. The test did not invoke SAM inference.

Cut movement using the actual cut marker keyboard event moved the cut from 75 to 76; the actual undo button restored the cut and controlled custom analysis ID. Browser errors and unhandled rejections were empty.

Evidence comprises `native-report.json`, `verify_timeline_native.py`, five per-case `*-final.png` actual media snapshots, `custom-frame65-reference.jpg`, fixture/server logs and isolated fixture data. PNGs capture the visible media element, not a full desktop screenshot. The read-image viewer was unavailable for this model, so conclusions rely on captured browser pixels, numeric comparisons, endpoint responses and state instrumentation rather than manual visual review.

The owned isolated service was PID 38980 on port 55835. It was terminated after the test; Windows exit code 1 is the expected terminate result. The port subsequently refused connection (`connect_ex=10061`) and the owned WebView window was destroyed. The user's existing port 50164 still returned HTTP 200. All background jobs were collected.

The final run was job `pwsh-874441c5cf9d489a`, exit 0. A prior early run passed an older HTML snapshot; a second attempt correctly refused that old hash before starting a server. Final conclusions use only the final frozen run recorded above.

Scope: actual Windows WebView2 DOM pointerdown/move/up handlers with approximately 30 ms event spacing, controlled immutable synthetic masks, and the production protected-video encoder. Synthetic pointer capture APIs on the timeline element are shimmed because DOM-generated pointers are not OS active pointers. No application source file was modified by this test. No foreground/AttachThreadInput API, physical OS pointer capture test, GPU inference, real user video or model quality evaluation is included.
