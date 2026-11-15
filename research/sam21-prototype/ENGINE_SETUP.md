# SAM 2.1 tiny official CPU engine

This directory is an isolated research prototype. Production files were not edited by the engine task. No SAM3 code or model is used.

## Run on this Windows machine

```powershell
Set-Location 'D:\财富密码\face-mosaic-prototype\research\sam21-prototype'
& '.\.venv\Scripts\python.exe' '.\smoke_engine.py'
```

The dedicated Python environment is `.venv`, Python 3.11.16. It borrows read-only packages from `../adaface-comparison/.venv/Lib/site-packages` through its own ASCII-escaped `borrowed_torch.pth`. The borrowed environment is unchanged. Torch is 2.15.0+cpu; torchvision 0.29.2+cpu lives in this dedicated environment. Imports were verified. Installed torchvision metadata requires torch>=2.14.0, satisfied by2.15.0; official SAM2 requires torch>=2.5.1 and torchvision>=0.20.1, also satisfied. This is machine-specific and depends on the borrowed environment; this is not a portable environment or EXE package.

`setup-engine.ps1` recreates the dedicated environment and CPU install using uv, requires the existing read-only adaface environment, and verifies/downloads the weights. The exact official source revision is already vendored under `vendor/sam2`. `requirements-resolved.txt` snapshots resolved packages (including borrowed packages). No GPU/CUDA toolkit is required. `SAM2_BUILD_CUDA=0` was set for editable official installation with `--no-deps --no-build-isolation`. The runtime uses CPU, torch inference mode, float32, four torch threads, and no model compile. Hole filling is disabled explicitly because upstream optional connected-component postprocessing needs the CUDA extension. Official dynamic multimask stability and point-memory binarization defaults remain enabled.

Installed app support in the dedicated env: FastAPI, uvicorn, python-multipart, OpenCV, NumPy, av, httpx, pywebview. The parent agent owns app launch instructions and UI files.

## Official source and checkpoint provenance

- Repository: https://github.com/facebookresearch/sam2
- Commit: `2b90b9f5ceec907a1c18123530e92e794ad901a4`
- Checkpoint: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
- Independently published official LFS pointer: https://huggingface.co/facebook/sam2.1-hiera-tiny/raw/main/sam2.1_hiera_tiny.pt
- SHA-256: `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`
- Bytes: `156008466`
- `models/provenance.json` records the successful verification. The engine verifies the complete hash before first deserialization. Official loader uses `torch.load(..., weights_only=True)`.
- `vendor/sam2/LICENSE`: Apache 2.0. Official README line 198 explicitly applies Apache 2.0 to model checkpoints, demo code, and training code. This prototype does not use the upstream demo font assets. Optional third-party CUDA components were not built.
- GitHub API hit anonymous rate limit; direct official git clone and raw official content were available.

## Contract

```python
from engine import SamEngine
engine = SamEngine()  # lazy: loads at first segment call
masks, timings = engine.segment(
    frames_dir,
    {2: [{'x': 323, 'y': 109, 'label': 1}]},
    frame_count=5,
    cancel_callback=lambda: False,        # optional, True requests cancellation
    progress_callback=lambda done, total: None,  # optional
)
```

Numeric JPEG filenames must be contiguous 0-based indices, for example `00000.jpg`, exactly equal to frame_count. Frames must have identical dimensions <=1280x720; count 1..150. JPEG decoding/normalization and internal 1024x1024 SAM preprocessing are official. Clicks use original frame pixels, not internal model coordinates. Output is `dict[int, numpy.ndarray]`, each mask uint8 HxW containing 0 and 1; each frame must be present. Object ID is always 1. Prompts can have positive/negative clicks; every prompted frame must include at least one positive. Negative correction clicks should be submitted together with the frame's positive clicks.

Every request starts a fresh inference state; all supplied prompt frames are registered as official conditioning frames before either propagation pass. Forward propagates from the earliest prompt to video end, reverse propagates from the same anchor to frame 0. Conditioning frame masks are retained by the official predictor. Re-submit the complete prompt dictionary after corrections. Model weights are cached, video inference state is reset/discarded per call. A lock serializes same-engine requests.

`total_seconds` excludes initial model loading but includes official frame state loading, point prompt inference and both propagation passes. `model_load_seconds` is reported separately (zero for warm requests); component seconds and seconds_per_frame are also returned. File validation happens before timed inference. Cancellation is cooperative between predictor operations, not inside torch kernels; raises `SegmentationCancelled` and returns no partial masks. Progress reports unique covered frames; repeated anchor callbacks can have the same count.

150 frames at source <=1280x720 still require substantial RAM: upstream holds 150 float32 3x1024x1024 image tensors (~1.8GiB before model/intermediate/state/masks). CPU mode is not real time and no maximum-memory benchmark has been made. Caller must impose its memory/time policy.

## Real video smoke

`smoke_engine.py` decodes the first five frames of the real Desktop/5.mp4 (25fps, source1280x720) and resizes them to640x360. A middle-frame positive click at(323,109) runs forward and reverse. A second call adds a positive+negative correction on frame4. It asserts full0..4 coverage, uint8 binary360x640 masks, the corrected positive pixel selected and negative pixel excluded, and cancellation. Results: `engine-smoke.json`, `smoke-masks.npz`, `smoke-mask-overlay.jpg`.

Final CPU smoke passed without CUDA warnings. Model loading5.35s (separate), initial five-frame segmentation28.04s (5.61s/frame), second call with two conditioning prompt frames33.86s. Components: initial loading3.37s, prompts3.25s, forward10.00s, reverse11.42s. Timings are short-clip measurements on this machine, not sustained throughput or maximum-size evidence.

Point prompting is spatial/object selection, not a semantic face detector. On this clip the initial selected region was ~26k pixels at640x360; correction substantially changed one prompt frame's area. This proves predictor execution and prompt response, not face accuracy or consistency quality. Visual review/ground truth is still needed.

Windows OpenCV Unicode path handling: `cv2.imwrite/imread` failed under this machine's Chinese directory path; smoke extraction/output therefore uses `imencode` + `Path.write_bytes`, `Path.read_bytes` + `imdecode`. PIL's official JPEG loader reads these paths successfully.
