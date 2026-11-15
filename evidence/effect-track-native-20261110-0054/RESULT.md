# Frozen effect track WebView2 acceptance

Result: PASS
HTML SHA-256: 6eff07d2858a1265e835ec803f17968f6c21316cdd4a6d9e6775cdfed78f2864
DOM checks: 95/95
Browser errors: []
Owned service: {'pid': 31868, 'url': 'http://127.0.0.1:50078/'}
Cleanup: {'owned_server_pid': 31868, 'exit': 1, 'webview_destroyed': True}
All frozen sources unchanged: True

Scope: real Windows WebView2 dispatched DOM PointerEvents with capture shim; controlled immutable analysis masks/boxes; real backend FFmpeg encoding and decoded output frames. No OS mouse input or model quality claim. User port 50164 untouched. Production files not modified.

First attempt used a 150-frame custom fixture for a 75-frame segment and correctly failed playback validation. Original failure retained in attempt1-fixture-mismatch.json. Fixed by adding controlled-custom-left (start 0, length 75), without production changes.

## DOM checks

- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: left trim commits one undo
- PASS: right trim sets half-open end
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: effect button exists 1
- PASS: click selects without modal
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: right inspector isolates selected effect
- PASS: effect button exists 1
- PASS: click selects without modal
- PASS: switch effect reflects strength
- PASS: video defaults do not mutate effects
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: body move translates both edges with one undo
- PASS: body undo restores effects
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: held drag blocks effect keyboard mutation Escape
- PASS: Escape leaves data and history unchanged
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: held drag blocks effect keyboard mutation pointercancel
- PASS: pointercancel leaves data and history unchanged
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: Ctrl+B splits selected effect only
- PASS: effect button exists 1
- PASS: click selects without modal
- PASS: Delete removes effect not video
- PASS: delete undo restores parameters
- PASS: automatic preview uses canvas frame 19
- PASS: unmasked outside regions 19
- PASS: automatic preview uses canvas frame 20
- PASS: black inside half-open region 20
- PASS: automatic preview uses canvas frame 49
- PASS: black inside half-open region 49
- PASS: automatic preview uses canvas frame 50
- PASS: unmasked outside regions 50
- PASS: automatic preview uses canvas frame 79
- PASS: unmasked outside regions 79
- PASS: automatic preview uses canvas frame 80
- PASS: automatic preview uses canvas frame 109
- PASS: automatic preview uses canvas frame 110
- PASS: unmasked outside regions 110
- PASS: automatic_regions_continuous continuous visible feedback
- PASS: automatic_regions_continuous exact final frame
- PASS: automatic_regions_continuous avoids full rebuild per move
- PASS: split actual video boundary
- PASS: split shifts right region to local coordinates
- PASS: split keeps left region clipped
- PASS: undo split restores whole local regions
- PASS: custom JPEG inside region is protected
- PASS: custom JPEG outside half-open region is original
- PASS: custom_regions_cached_continuous continuous visible feedback
- PASS: custom_regions_cached_continuous exact final frame
- PASS: custom_regions_cached_continuous avoids full rebuild per move
- PASS: custom_regions_cached_continuous single in-flight preview body
- PASS: custom_regions_cached_continuous no held-drag abort storm
- PASS: custom_regions_cached_continuous no busy preview response
- PASS: custom_regions_uncached_continuous continuous visible feedback
- PASS: custom_regions_uncached_continuous exact final frame
- PASS: custom_regions_uncached_continuous avoids full rebuild per move
- PASS: custom_regions_uncached_continuous single in-flight preview body
- PASS: custom_regions_uncached_continuous no held-drag abort storm
- PASS: custom_regions_uncached_continuous no busy preview response
- PASS: rapid custom DOM reselect and slider settles on latest protected frame
- PASS: rapid custom DOM reselect and slider has no busy preview responses
- PASS: mixed cut moves 90
- PASS: mixed modes retained 90
- PASS: mixed caches invalidated 90
- PASS: explicit effects remain selectable after invalidation 90
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: pending effect selected without analysis ready 90
- PASS: custom own interval and target retained 90
- PASS: automatic own absolute intersection 90
- PASS: newly extended gap unmasked 90
- PASS: cut single undo 90
- PASS: mixed undo restores original config and analysis 90
- PASS: mixed cut moves 60
- PASS: mixed modes retained 60
- PASS: mixed caches invalidated 60
- PASS: explicit effects remain selectable after invalidation 60
- PASS: effect button exists 0
- PASS: click selects without modal
- PASS: pending effect selected without analysis ready 60
- PASS: custom own interval and target retained 60
- PASS: automatic own absolute intersection 60
- PASS: newly extended gap unmasked 60
- PASS: cut single undo 60
- PASS: mixed undo restores original config and analysis 60

## Encoded artifacts

- automatic-regions-export: 150 frames; [{'type': 'video', 'codec': 'mpeg4'}, {'type': 'audio', 'codec': 'aac'}]; SHA-256 efe304ec4b7fcea4dc951ef6dc3e8b1fbccef326c6f1c6a7a23cf5dbd55c9c05. Boundary center checks inside black [20,50) at frames 20/49 and outside at 19/50/79/110 passed.
- custom-regions-protected: 150 frames; [{'type': 'video', 'codec': 'h264'}, {'type': 'audio', 'codec': 'aac'}]; SHA-256 c46d30458f21d5de487bb7b11514fb4c1c829721a242a79d1ad2a5d606845372. Boundary center checks inside black [20,50) at frames 20/49 and outside at 19/50/79/110 passed.
- custom-regions-export: 150 frames; [{'type': 'video', 'codec': 'mpeg4'}, {'type': 'audio', 'codec': 'aac'}]; SHA-256 5f2efe1eb3cbffc4ae62d74650a12332e573c1a24cac0a52d0847d0bea9b38ce. Boundary center checks inside black [20,50) at frames 20/49 and outside at 19/50/79/110 passed.
