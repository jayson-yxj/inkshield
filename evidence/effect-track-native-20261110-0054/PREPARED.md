# Effect track WebView2 acceptance preparation

State: READY FOR PARENT FREEZE / FINAL SELECTORS. No acceptance execution yet.

Harness: verify_mask_timeline_native.py, copied from ../mask-timeline-native-20261110-0024/verify_mask_timeline_native.py. Prior suite retained as legacy_dom_suite.reference.js only; its modal assumptions must not be run against the new interactions.

Dependency preparation succeeded with .venv-sam-build/Scripts/python.exe --prepare: av, numpy, PIL, pywebview, imageio-ffmpeg available; legacy instrumentation compiles. No service started. User port 50164 and persistent job pwsh-28449159f972428e untouched. No production source changes.

Execution gate: explicit parent freeze.json including index.html, server.py, preview_video.py, sam_service.py, mask_timeline.py, sam_engine.py; finalized DOM selectors and event contract. Harness checks all hashes before execution, checks served HTML, and checks sources again after execution.

Planned new interaction cases (all editing via DOM handlers; read-only state observations):
- Click effect selects without opening dialog; existing right-side style/intensity/target controls modify only selected effect, preserve other effect configuration and video boundaries.
- PointerEvent left/right edge trims and body moves, record before/after state, 14 actual DOM dispatched pointer events per operation; verify clamp/overlap behavior and undo.
- Switch selected effects and verify right-side values reflect each effect; select video and edit defaults without mutating any existing effects.
- Effect Ctrl+B splits only effects, leaves video boundaries unchanged; Delete targets selected effect and never deletes a selected video cut by mistake.
- Escape and pointercancel during effect drag leave data unchanged; successful pointer drag produces exactly one undo entry.
- Selected effect split at playhead, delete, undo; preserve half-open integer local frame ranges.
- Real automatic canvas preview boundary frames 19/20/49/50 and 79/80/109/110; black interval [20,50), mosaic interval [80,110).
- Real DOM-triggered exports and custom protected video; decode 150 frames and AAC audio, inspect black center inside [20,50), unmasked center at 19/50/79/110.
- Automatic/custom cached/custom uncached scrub continuous visible feedback and exact final frame; queue in-flight-body/abort/429 regression and rapid custom reselection.
- Mixed automatic/custom neighboring video cut pointer drag both directions; each segment retains mode and only its own absolute region intersection, newly extended gap has no effect; analysis/cache invalidation and undo restores complete original state.

Scope: real Windows WebView2 with dispatched DOM PointerEvents and synthetic pointer-capture shim inherited from legacy instrumentation. Not OS mouse input. Synthetic immutable masks/boxes are controlled backend analysis fixtures; no model accuracy/quality claim. Real FFmpeg encoding/decoding. Only owned random-port test server and owned WebView2 cleaned up.
