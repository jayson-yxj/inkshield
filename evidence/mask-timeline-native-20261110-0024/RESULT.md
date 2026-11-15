# Windows WebView2 mask-timeline native acceptance

Final source freeze: `index.html` SHA-256 `e21ad6a53b9c08f85b2cb980e7a01c0a21a241b56f6707a88eea1362345160e2`; the other five application files are pinned in `freeze.json`.

Final result: **PASS**, 51/51 actual DOM assertions, 0 browser errors, 0 HTTP429 responses. All six source files matched the freeze both before and after execution. Final managed job `pwsh-ebf3d1fe42af4e38` exited 0.

The final report is `native-report.json`; the isolated server PID 40180 was terminated after the run and the WebView window was destroyed. The server's exit 1 records intentional Windows termination, not an acceptance failure.

Verified editing: legacy undefined whole-segment region; local crop; independent second region and strength; overlap rejection without commit; crop and delete undo; video boundaries unchanged by region edits; modal keyboard isolation; split at frame 75 shifts right [80,110) to local [5,35), keeps left [20,50), and undo restores both; deleting every region yields explicit [] and undo restores the last one.

Verified previews: automatic canvas frames 19,20,49,50,79,80,109,110; custom JPEG inside/outside the region; protected video playback; cached and uncached custom drag; four real DOM segment-reselection plus immediate slider input/change cycles settle to protected frame 49 with no busy responses.

| Drag | Pointer events | Full timeline rebuilds | Distinct visible frames during held drag | Aborts during held drag | Final frame |
|---|---:|---:|---:|---:|---:|
| Automatic | 51 | 0 | 22 | 0 | 140 |
| Custom cached | 50 | 0 | 12 | 0 | 65 |
| Custom uncached | 50 | 0 | 13 | 0 | 65 |

Three real encoded assets were downloaded and decoded with PyAV. All contain exactly 150 video frames and AAC audio. Ordinary automatic/custom exports use MPEG-4; custom protected playback uses H.264. Each asset has center mean RGB 0 at frames 20 and 49, and >125 at frames 19,50,79,110, demonstrating local [20,50) masking boundaries. The second [80,110) region uses independent mosaic strength 35.

Evidence images include `auto-frame-19.png` through the eight sampled automatic boundary frames, `custom-inside-preview.png`, and `custom-outside-preview.png`. Encoded assets are `automatic-regions-export.mp4`, `custom-regions-protected.mp4`, and `custom-regions-export.mp4`.

Scope: real Windows WebView2 DOM events, file input import, independently editable local half-open mask regions, real backend JPEG/protected-video/export encoding and PyAV frame decoding. Controlled immutable rectangle masks and automatic face boxes are injected as analysis fixtures. No GPU inference or packaging is claimed. The test starts its own random-port server and never calls or stops user service 50164. Settings are edited through DOM controls; fixture injection changes analysis cache identity only.

Earlier evidence: `native-report-pre-singleflight.json` records all 49 DOM assertions passing on the prior source. That run's overall result failed because the acceptance harness incorrectly required H.264 for ordinary exports; production ordinary export uses MPEG-4 + AAC. Initial testing also exposed HTTP429 after rapid custom selection plus immediate slider editing; the final source adds global single-flight JPEG handling, and the final suite adds four rapid actual DOM reselect/input/change cycles with an exact final protected frame and no HTTP429 requirement.
