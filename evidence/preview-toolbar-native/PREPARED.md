# Preview and toolbar native acceptance preparation

State: FINAL FULL NATIVE PASS: 54/54 checks, browser errors0, ten source hashes unchanged, owned service PID39944 exited. Authoritative full result is [native-report-final-pass.json](native-report-final-pass.json), also copied as latest [native-report.json](native-report.json). Final index SHA9b65673074d99879ba2d3c0ed5acd2c22572157ecf6924b1bea32a39fe4aa894 and layers SHAc6d21dada466498e5c4d25e13dbe39e89f64eabc3dc15a3cb8d881a5d1c86287. No diagnostic play intervention was loaded. Evidence history is in [README.md](README.md); media-play-probe is diagnostic only, never full acceptance. The preparation plan below is historical and does not assert all proposed cases ran.

Ownership: this new directory only. Live50164 remains untouched; no packaging/inference. Reuses successful real WebView2 harness: _base_executable plus inherited PYTHONPATH, owned ephemeral-port service, PID/source hash gate, controlled immutable analyses, synthetic pointer-capture bookkeeping, WebView2 CapturePreviewAsync and CDP reduced-motion support.

Planned frozen test cases:
1. All-pending layers: selected segment and continuous multi-segment preview run as original video, visible pending-layer warning, reach final frame and replay; export remains disabled.
2. Ready automatic + active pending custom: ready automatic mask must remain visible in the displayed preview (capture ROI/pixel evidence, not only state). Pending layer is skipped with visible warning. Run across cut boundaries to final frame and replay. Export remains strict for incomplete stack.
3. Additional ready custom + pending layer: protected-video aggregate uses ready layers only and transitions between protected and all-pending source segments. Fixture identities must exactly match segment frame bounds; add short/head fixture identities only after final interval contract is known.
4. Single visible split/delete/undo tools: exercise video split/merge/undo and effect split/delete/undo using the same controls. Preserve layer/absolute-region state and confirm legacy effect-specific controls hidden.
5. Import control follows automatic/custom theme; sample actual computed foreground/background/border at start, intermediate frames and settled state. Capture actual app screenshots with stable frame and no model inference.
6. Three workspace panel toggles display 收起/展开 with panel name, aria-expanded matches actual panel geometry; collapse and restore each, verify tools remain reachable.

Current selector contract from parent: #splitBtn / #deleteCut / #undoSplit; splitTimelineSelection()/deleteTimelineSelection() public routing; splitVideoSelection() layer override; #splitMaskRegion/#deleteMaskRegion hidden compatibility. Need final pending-warning selector and final panel selectors before execution.

Prepared suite helpers intentionally stop before cases; this cannot be mistaken for completed acceptance. Final report must bind source/harness/suite/fixture hashes and preserve failed attempts. Native image captures are not claimed visually inspected because current model does not support image input.
