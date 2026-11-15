# Preview, shared toolbar and theme native evidence

Owner scope: evidence/preview-toolbar-native only; production changes belong to the parent agent. The live service at port 50164 was not touched. Tests launch an isolated service on a random port, run actual Edge WebView2 with synthetic DOM input, and terminate the owned process in finally. Controlled immutable analysis fixtures avoid inference. This is source native acceptance, not packaged-product acceptance.

## Final full native result

PASS: 54/54 checks, zero browser errors, all ten production hashes unchanged. The authoritative final full report is native-report-final-pass.json; native-report.json contains the same final run. Job pwsh-19129947babd41c6 completed with exit code0 and owned service PID39944 was confirmed exited. Final index.html SHA256 is 9b65673074d99879ba2d3c0ed5acd2c22572157ecf6924b1bea32a39fe4aa894; layers_ui.js SHA256 is c6d21dada466498e5c4d25e13dbe39e89f64eabc3dc15a3cb8d881a5d1c86287. Raw slider synchronization, aggregate slider25/0, both two-segment playback/replay cases passed. Protected preview ROI MAE against raw was45.41. Reduced-motion icon/viewer/ring transitions were0s.

This final run used the original slider input/change operations and no diagnostic play intervention. native-report-media-play-probe.json is diagnostic_only=true and is NOT full acceptance: it recorded synchronous seeks0→5.56→0 before the final selection fix, and an unsuccessful diagnostic play attempt. Its passed flag describes completion of that diagnostic only.

## Evidence chain

- native-report-main-pass.json: initial 52-check full pass, using timeline Home for the all-pending playback start. This did not cover the raw slider synchronization regression.
- native-report-slider-probe.json: original frozen code regression. End gave globalFrame=149, slider=149, sourceTime=5.96; slider input25 gave globalFrame=149, slider=25, sourceTime=1.0. Continuous playback subsequently started from zero instead of the slider position.
- native-report.json: latest full execution; read passed, dom.checks, source_hashes_after and browser_errors for authoritative result. Updated suite restores slider input0 for all-pending playback, and checks aggregate slider25 then0 against globalFrame.
- native-report-postfix-startup-diagnostics.json: updateFrameLabel candidate reproduced first continuous playback timeout with source time0, seeking=true and readyState1; 33 preceding checks passed, browser errors0.
- native-report-c6d21d-timeout.json: same-target seek guard candidate also failed at that playback start, with the same observed source state and 33 passing preceding checks. The guard alone did not resolve the native failure. This does not identify a Chromium internal cause.
- freeze.json: ten production SHA256 values for the latest run; layers_ui.js is c6d21dada466498e5c4d25e13dbe39e89f64eabc3dc15a3cb8d881a5d1c86287. Previous updateFrameLabel-only candidate was 949153f0e59ce47b49339555e8dc86906cb4977f69d68e333d1ec06dd782e520.
- fixture-hashes.json binds fixture code and six-second input video. Each native report binds its suite and harness hashes.
- actual-app-custom.png and actual-app-automatic.png are actual WebView2 CapturePreviewAsync captures from the latest execution. They have not been visually reviewed by the model.

## Full suite coverage

Actual mode toggle samples newly queried header, import control, viewer, active video clip and active layer at settled automatic, immediately after switching, 100ms and settled custom. It verifies intermediate colors and rebuilt layer identity. No timeline-mask exists at theme sampling time, so its theme is not asserted. Reduced-motion CDP emulation verifies icon, viewer and ring transitions are zero seconds.

All three panels check Chinese collapse/expand labels, aria-expanded/aria-hidden, inert, reachable restore controls and restored geometry. Shared toolbar checks effect split/delete/undo and video split/merge/undo; legacy effect-only toolbar controls remain hidden.

Playback tests cover all-pending two-segment natural end and replay, then ready-automatic plus active-pending-custom protected head followed by all-pending tail, natural end and replay. Each run samples actual media clock advancement and both segment identities. Fixed-frame protected preview is compared with decoded raw-frame ROI, while strict export payload rejects pending layers and export control remains disabled. Pending and incomplete-protection warnings are checked.

Limitations: no SAM inference, packaging, visual screenshot review, or ready-custom fixture case in this suite. PREPARED.md is a historical preparation plan, not an assertion that every planned variant ran.
