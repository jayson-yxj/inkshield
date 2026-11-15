# Layers and workspace native acceptance

**Result: PASS.** Frozen source hashes and acceptance hook hashes are recorded in `freeze.json`, `integration.json` and `native-report.json`.

- 114 browser checks passed; no browser errors.
- JPEG: 90 ROI comparisons; maximum MAE 0.4258 / 12.
- layers-protected: 90 ROI comparisons; maximum MAE 5.6958 / 12.
- layers-export: 90 ROI comparisons; maximum MAE 4.8783 / 12.
- Continuous scrub: 47 synthetic moves/events, 20 distinct visible samples, 0 timeline rebuilds, peak 1 preview request, 0 held-drag cancellations; exact final frame and no 429 checked.

## Coverage

One automatic and two independent custom layers created by DOM; nonactive-layer trim, per-layer overlapping temporal intervals and independent strength/style; active-only explicit empty deletion, reselection and full-stack undo. Three panels collapse/expand with intermediate geometry, shared zoom/pan, stale SAM display rejection and selected-layer source-coordinate request attribution. Natural automatic-to-final-custom handoff for 10-frame and 2-frame tails; each retains final frame 149 in protected video with a black custom ROI. A separate synthetic source-ended event exercises the fallback and is not counted as natural source-ended evidence. Same-segment aggregate ended selects local frame 149; a second DOM play starts from the beginning (protected currentTime < 1 second).

15 sample frames: 0,19,20,39,40,59,60,80,99,100,119,120,139,140,149. Six ROIs cover exclusive layers, overlaps and outside area. Independent explicit layer loop composes from decoded source using existing single-mask primitives, never aggregate/output routes. Reversing layer order changes overlap MAE by 24.22–27.02, above the 12 threshold. JPEG references include local quality-88 compression; H264 and export use raw composed references.

## Scope and limitations

Real Windows WebView2 and real backend encoding/decoding on an isolated random-port service. Input is synthetic DOM PointerEvent/WheelEvent/KeyboardEvent, not operating-system mouse input. Controlled immutable mask fixtures replace model inference; SAM preview response is a controlled empty result while production UI handlers construct and attribute the real request. This does not establish model propagation accuracy. Backend seven successive SAM analyses are mocked-inference tests referenced by BACKEND_LAYERS_REVIEW.md; no claim of seven real model runs.

## Attempts and cleanup

Two initial hash-gate stops caught concurrent SAM-hook edits before service launch. Three failed browser attempts are retained: fractional MouseEvent coordinates vs integer event coordinates; split segments sharing layer IDs required a segment-qualified test selector; raw-vs-JPEG reference mismatch diagnosed as codec loss (raw OpenCV/PyAV MAE 0; local JPEG88 vs browser ROI MAE 0.2008). These were acceptance-fixture corrections, not observed production failures. A fourth full candidate pass is retained separately before final replay regression.

Final owned service PID 32708 terminated, WebView destroyed; all source hashes unchanged: True. User service port 50164 was never contacted or modified. Termination exit 1 is expected on Windows. Every tracked background job was collected.
