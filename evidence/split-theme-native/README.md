# Frozen split/theme native acceptance

Final result: PASS, 55/55 DOM checks, zero browser errors. See native-report.json for complete checks, computed CSS samples, region snapshots and before/after source hashes. All ten frozen source hashes remained identical. Production sources were not modified.

Runtime: real Windows Edge WebView2 via pywebview (gui=edgechromium), production HTTP application on owned random port 55017, PID 24104, terminated after acceptance. Live port 50164 untouched. Input: controlled 6-second video and immutable analysis fixture; synthetic DOM click/input/PointerEvent interaction. Pointer capture uses the established native harness bookkeeping shim because synthetic pointers do not have OS capture. No inference, packaging, export or broad backend acceptance claimed.

Verified:
- One and three visual rows retain distinct geometry through repeated split into three segments, merge, undo merge, and repeated merge back into one segment.
- Absolute per-frame effect coverage and effect configuration survive these operations, including a DOM-trimmed nonfull [15,135) interval. Coverage includes style, strength, targets, faceShape, faceMode, personIds and includePending.
- Sole 添加图层 control adds exactly one default automatic layer. Mode toggle changes the same layer identity and preserves other layers.
- Automatic green #b8ed80 and custom lightblue #aedcff root themes; ambient shadow changes with a measurable intermediate sample at 110ms; icon CSS matrix and actual bounding geometry change during rotation.
- Undo restores automatic mode/theme without adding a layer; selected effect disables mode toggle.
- WebView2 CDP reduced-motion emulation yields matching media query and 0s computed icon/viewer/ring transition durations.

Screenshots actual-app-custom.png and actual-app-automatic.png are native CoreWebView2.CapturePreviewAsync PNG captures, 1808×1104. They capture the final app at the same frame with custom/automatic toggles. Screenshot images were captured but not visually reviewed: this model does not support image input. No title/control overlap or top-right icon-placement assertion was added after the run; recorded icon geometry verifies rotation only.

Startup issues resolved within harness: Windows venv launcher PID mismatch; base interpreter required inherited PYTHONPATH. Initial real-browser attempt stopped on missing synthetic pointer-capture bookkeeping; retained as native-report-pointer-fixture.json. Final native-report.json passed after applying the established harness shim. Source freeze was unchanged throughout.

Harness: native_acceptance.py; focused interaction suite: suite.js; source hashes: freeze.json. Final report binds suite and harness SHA256. Reusable fixture provider is the existing evidence/layers-workspace-native-20261110-0122/controlled_fixtures.py. Only this evidence directory was written.
