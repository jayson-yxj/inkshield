# Windows WebView2 timeline acceptance preparation

Prepared only; actual run requires parent freeze hash.

Run with the project `.venv-sam-build/Scripts/python.exe`:

```text
verify_timeline_native.py --execute --html-sha256 <parent-frozen-index-html-sha256>
```

This evidence-only script imports the isolated controlled fixture server from `../sam-smooth-playback-20261109-2340/verify_smooth_native.py`. Masks are immutable NumPy arrays. It generates a six-second H.264/AAC synthetic source and uses the application's real protected-video encoder. It does not load a SAM predictor or perform GPU inference. The user's server on port 50164 is not accessed or stopped.

The actual Windows WebView2 window receives DOM PointerEvent pointerdown/move/up events every approximately 30 ms for 1.5–2 seconds. Synthetic pointers are not native active pointers, so pointer capture APIs on the timeline element alone are shimmed to track capture. No application timeline, seek, preview, selection, rendering, or click handler is replaced; renderTimeline/fetch are wrapped for observation. No foreground or AttachThreadInput APIs are used. This verifies the DOM handler path in WebView2, not physical OS mouse capture.

Cases: cached automatic geometry, unanalysed raw video, custom with an existing encoded protected-video cache, custom without that cache, cross-segment raw-to-custom, stale samDisplayed click rejection, cut keyboard move and undo. Both custom cache states are expected to scrub through the JPEG path.

Measurements include pointer event count and duration; renderTimeline calls; preview requests, abort signals, and peak in-flight response bodies; sampled visible media IDs, pixel hashes, center pixels, decoder times and decodedSourceFrame; final global/local frames and custom samDisplayed ownership. Per-case final media PNGs and JSON report are written here. Cleanup terminates only the owned isolated server and created WebView window. The source HTML hash is checked before start, against served bytes, and after cleanup.

The stale displayed-frame click case explicitly marks the browser-side SAM capability as available and warmup ready, solely to pass the capability gate and reach the real displayed-frame rejection guard. No prompts are added and no SAM endpoint is called in that case.

Scope excludes real user video, model inference/quality, physical pointer capture, and GPU performance. Visible media PNGs capture the actual video/image/canvas element, not the complete desktop window.
