# Backend ordered layers review

Date: 2026-11-10 (Asia/Shanghai). Scope: backend implementation and inference-free regression, before parent-managed service restart / frontend acceptance.

## Contract

- GET `/api/preview/{analysis_id}` accepts `layers` JSON query.
- POST `/api/export/{analysis_id}` and `/api/custom-playback/{analysis_id}` accept `layers` JSON form.
- Value is ordered `[{"analysis_id":"...","mask_regions":[...complete existing camelCase region configs...]}]`.
- Missing layers preserves legacy behavior. Explicit `[]` applies no effects but still requires a valid anchor analysis in the URL. Supplying both layers and mask_regions returns 422.
- All layer analyses must have the identical resolved source path, segment start, frame count, fps, width and height. Cross-layer overlap is allowed; within-layer overlap is rejected. Each layer independently validates people/targets/configs.
- Frozen layer/config snapshots are applied in array order through one per-frame compositor used by JPEG preview and export; protected H264 preparation calls that same export compositor before transcoding protected pixels.
- Canonical cache identity includes anchor, ordered layers, each analysis ID and complete normalized regions; object field order does not matter. Target/person ID sets are sorted. Layer order matters.

## Lifecycle

- Removed the fixed five-SAM-results admission limit. Published masks are one `.npy` per frame, opened with `np.load(..., mmap_mode='r', allow_pickle=False)` only when requested. No persistent mmap handle array or duplicate persisted PNG array.
- Publication validates every shape. DiskMasks retains a small manifest; later validation checks file stat signatures without loading every frame. Missing or modified manifest files are rejected; requested frame dtype/shape is checked again. Existing tuple fixtures retain full validation.
- SAM disk admission estimates frame scratch/result storage and requires another 256 MiB free; insufficient disk returns HTTP 507 with a readable message. Playback preparation also checks disk capacity. Filesystem failure after admission remains possible and is reported as task failure.
- Existing published results remain on disk; no automatic deletion of possibly used results. Failed unpublished SAM directories and extracted temporary frames are cleaned up. There is no claim of cross-process analysis registry restoration: service restart still loses in-memory JOBS/ANALYSES registry.
- Playback reuse index is a 12-entry LRU; completed/error entries can leave the index without deleting previously published URLs. Active workers remain bounded by the original two job slots; an index containing only active entries returns busy instead of adding work. Disk files can accumulate and admission eventually refuses additional work; retention is intentionally not automatic eviction.

## Verification

Command:

```powershell
.\.venv-sam-build\Scripts\python.exe -m unittest test_face_backend test_mask_timeline test_preview_video test_mask_layers tests.test_sam_integration tests.test_sam_propagation tests.test_sam_warmup -q
```

Final result: **51 tests passed in 12.624 seconds**, exit 0.

Coverage includes real automatic + two independent SAM cached-mask composition in JPEG, actual H264 preparation and MP4 export decoded-pixel checks; zero layers; source/range/fps/dimension mismatch; malformed layers; ordered compositor calls; cross-layer overlap and rejected within-layer overlap; canonical reuse and order invalidation; read-only disk result access; manifest corruption; low disk; preview LRU retaining old URL; seven successive mocked SAM analyses all readable and immutable; existing empty-mask, propagation, warmup, audio, odd dimensions, styles, worker failure and slot release regressions.

Limitations: SAM inference in these integration tests uses test doubles; this run does not prove real model propagation quality or real frontend interaction. Actual video encoding/decoding is exercised. No HTML changes, running 50164 stop/restart, or packaging were performed by this backend agent. Static whitelist routes for workspace_ui.js, workspace_ui.css and layers_ui.js were added.

## Code SHA-256 at review

| File | SHA-256 |
|---|---|
| server.py | 53FC8EBB1F925137AB8F75C9652E3802EF8E8EC1689C2EDF4926E2486E3E33C0 |
| preview_video.py | F6F1A958E0A4372B9551CED8FC2E011990AB32E5EAB92EA978D4DB6082A4D5AD |
| mask_timeline.py | 1B04663002EE3703A1E5F3F8B2C2E9332E8678AEDCAC828CB8598D82ADEABD38 |
| mask_layers.py | 6B4B41C56637430B47C9A20F27FEA4FD401E146BE8643AE038F78BB42F3D3476 |
| sam_service.py | 2DC72ACCC22F537C23CC04F7334B65814F5A091569919CDD1CDBCE89C5588465 |
| test_mask_layers.py | 8F64E63C5F7FD39ED8478EE0E2902065B9CF89C9FAFFC68161912668CC00C6FA |
| tests/test_sam_integration.py | 09642C17EC600FDC5B49BD55E4CCFE0507BAFA01169F7B7FDCEA1B4C76C50DDD |

## Independent frontend transport review (snapshot, not final frontend acceptance)

Read layers_ui.js after backend completion. Payload field names, query/form encoding, local preview frame and status/url handling match the endpoint contract. Omitting effect-free layers is valid when any same-segment ready analysis supplies the anchor.

Sent parent two findings for frontend owner resolution: (1) every layer effect-free and unanalysed yields stackReady=true but stackAnchor='', causing missing-anchor endpoint URLs in JPEG/clip playback/export; raw playback or disable/export analysis acquisition must handle this state. (2) continuous source playback checks stackNeedsVideo for effect-free multilayer segments and may hand off repeatedly to the same segment. These are review findings, not verified runtime failures; no frontend changes made by backend agent.
