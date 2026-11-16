# SAM 2.1 Windows portable packaging

Repository layout note (2026-11-16): this document retains historical build evidence below. Current tools are in `tools/build` and `tools/release`, specs in `packaging/pyinstaller`, frontend in `src/inkshield/web`, and dependency metadata in `packaging/PACKAGING_DEPENDENCIES.json`. Commands run from the repository root. The local `research` vendor checkout is not supplied by a clone; obtain and verify the recorded upstream source before reproducing SAM builds. Historical source freezes and artifact hashes do not certify this reorganized checkout.

Current release (2026-11-10): reviewed 12-file production freeze, including tutorial v03, is being built into `dist/inkshield-20261110/Inkshield`. The 2026-11-09 figures below are historical baseline evidence and do not certify this release. Final acceptance and archive details are recorded in the release report and runtime evidence after completion.

The current build includes layers_ui.js, workspace_ui.js, workspace_ui.css and the mask_layers, mask_timeline and preview_video backend modules. build_verified_release.py checks the reviewed source before and after compilation, then records BUILD_PROVENANCE.json. Matrix, legacy and actual desktop acceptance bind to the exact EXE path, source freeze and bundled frontend hashes. HTTP checks cover the main page, tutorial, startup and three workspace assets. The native matrix also opens the tutorial through the real frozen app entry.

package_sam_release.py requires all three acceptance gates and successful cleanup before creating the new Chinese release ZIP. It refuses overwrite, excludes SHA256.json from its own inventory, checks CRC and streams every ZIP member for SHA256/size/name-set verification, including the embedded manifest. Failed archives are retained for diagnosis; retries require a new path. No screenshot-based human visual review is claimed.

## Scope and environment

Only the new `.venv-sam-build`, `inkshield-sam.spec`, `build_sam_exe.ps1`, this report, and associated new build outputs belong to this task. Existing `.venv`, research environments, original `inkshield.spec` and `build_exe.ps1` are unchanged. No SAM3 is included.

Native Windows x64 CPython 3.11.16 is selected with uv 0.12.18. The existing `requirements/packaging.lock.txt` is the formal application/package baseline, including CPU onnxruntime 1.23.2, PyInstaller 6.22.3 and PyAV 16.0.1. SAM additions are official torch 2.7.1+cu126, torchvision 0.22.1+cu126, hydra-core 1.3.2, omegaconf 2.3.0, iopath 0.1.10, huggingface-hub, tqdm and Pillow. Startup warmup prefers available CUDA and reports CPU fallback reasons. The capabilities API keeps a compatibility default_device='cpu' field; the UI adopts the successful warmup device unless manually changed. Explicitly selected devices do not silently fall back.

Hardware observed 2026-11-09: NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB VRAM, driver 572.83. `nvidia-smi` reports CUDA compatibility 12.8, sufficient for the selected CUDA 12.6 wheel runtime. Official wheel Content-Length responses: Torch 2716982502 bytes and Torchvision 6334229 bytes, totaling 2723316731 bytes (excluding support packages). Approximately 1756 MiB VRAM was occupied before testing. A local CUDA toolkit is not required. GPU availability and real predictor inference results will be recorded below after preparation.

## Current source preparation and supported layouts

The supported application layouts are an editable source installation and the PyInstaller distribution. Ordinary application wheel resource inclusion is not promised. A fresh clone does not include SAM source or weights. Before enabling SAM, prepare the official source at the pinned commit and the checkpoint described below, retaining upstream license/provenance files.

For editable source execution, resource lookup defaults to the repository root. The engine requires both `models/sam2.1_hiera_tiny.pt` and the physical file `vendor/sam2/sam2/build_sam.py`, plus importable Torch. Installing `sam2` with pip alone does not satisfy this vendor-file check. From the repository root, prepare a new vendor directory (do not replace an existing checkout without checking it):

```powershell
git clone https://github.com/facebookresearch/sam2.git vendor/sam2
git -C vendor/sam2 checkout 2b90b9f5ceec907a1c18123530e92e794ad901a4
git -C vendor/sam2 rev-parse HEAD
# Place the official tiny checkpoint in models/sam2.1_hiera_tiny.pt.
# Its SHA256 must equal 7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69.
Get-FileHash models/sam2.1_hiera_tiny.pt -Algorithm SHA256
$env:SAM2_BUILD_CUDA = '0'
uv pip install --python .venv-sam-build/Scripts/python.exe --no-deps --no-build-isolation -e vendor/sam2
uv pip install --python .venv-sam-build/Scripts/python.exe --no-deps -e .
.\.venv-sam-build\Scripts\python.exe -c "from inkshield.sam_engine import resource_paths, capabilities; print(resource_paths()); print(capabilities())"
```

Create the environment and install the dependencies shown in the historical reproduction section first. If a verified checkout already exists elsewhere, set `$env:INKSHIELD_SAM_VENDOR = 'C:\path\to\sam2'` instead; this directory must contain `sam2/build_sam.py` and upstream configs. `INKSHIELD_SAM_MODEL` similarly overrides the checkpoint path. Use absolute paths and set these variables in the process that launches the application or build. The retained historical research checkout can be selected explicitly this way; it is not the default source runtime location.

The PyInstaller spec can fall back to the installed `sam2` package when collecting vendor resources. Successful collection does not make a source launch independent of its physical vendor directory. Frozen runtime resources must still contain `vendor/sam2/sam2/build_sam.py`; validate the resulting bundle and optional-model capabilities independently.

## Historical environment reproduction

Run from the project root in PowerShell. The historical research vendor path below requires a separately prepared local checkout, or replace it with the current `vendor/sam2` directory above:

```powershell
uv venv --python 3.11.16 .venv-sam-build
uv pip install --python .venv-sam-build/Scripts/python.exe torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
uv pip install --python .venv-sam-build/Scripts/python.exe -r requirements/packaging.lock.txt hydra-core==1.3.2 iopath==0.1.10 omegaconf==2.3.0 huggingface-hub tqdm pillow
$env:SAM2_BUILD_CUDA = '0'
uv pip install --python .venv-sam-build/Scripts/python.exe --no-deps --no-build-isolation -e research/sam21-prototype/vendor/sam2
# Invoke only after the application source freeze is confirmed:
.\.venv-sam-build\Scripts\python.exe tools/build/build_verified_release.py
```

Upstream SAM2's optional CUDA connected-component extension is disabled. The application sets hole filling to zero. CUDA tensor inference uses the official wheel libraries.

## Layout and runtime dependencies

Initial completed payload inventory: 4071 files, 4623379468 bytes (approximately 4.31 GiB; report copy and later release metadata may slightly change this total). CUDA DLL inventory includes torch/lib cublas64_12.dll, cublasLt64_12.dll, cudart64_12.dll, cudnn64_9.dll, cudnn_adv64_9.dll, cudnn_cnn64_9.dll, cudnn_engines_precompiled64_9.dll, cudnn_engines_runtime_compiled64_9.dll, cudnn_graph64_9.dll, cudnn_heuristic64_9.dll, cudnn_ops64_9.dll and torch_cuda.dll; torchvision also retains its own cudart64_12.dll. The large portable payload is expected for the bundled CUDA runtime.

Current target: `dist/inkshield-20261110/Inkshield/Inkshield.exe`, with `_internal` and resources in the same portable folder. Copy/extract the whole folder. Python and the build environment are not runtime prerequisites. The desktop shell requires Microsoft Edge WebView2, as in the existing formal desktop application. GPU mode requires a compatible NVIDIA driver; startup warmup prefers usable CUDA and falls back to CPU with a reason.

The spec retains the original System32 VC runtime pins and fails if analysis imports Anaconda DLLs. PyAV's av.libs FFmpeg DLLs, CPU ORT and OpenCV video codecs are included. PyInstaller's Torch/Torchvision hooks remain active and explicit dynamic-library collection retains CUDA runtime DLLs. SAM2, Hydra, OmegaConf and iopath are collected with their configuration resources. Official SAM2 runtime .py/.yaml files are additionally preserved under `vendor/sam2/sam2` for the engine's physical resource check. Research scripts, source repository metadata, models unrelated to the existing formal app and development FFmpeg executables are excluded.

`-CreateZip` is rejected to prevent bypassing acceptance gates. After acceptance, package_sam_release.py creates a ZIP64 archive and records SHA256. The executable remains an onedir application and must stay with its adjacent files. Artifacts are unsigned.

## Model/source licensing and provenance

The parent agent copied the model and proof to `models/sam2.1_hiera_tiny.pt`, `models/SAM21_SOURCE.md`, `models/SAM21_PROVENANCE.json`, and `models/SAM21_LICENSE.txt`.

Official source: https://github.com/facebookresearch/sam2 at commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`. Official checkpoint: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt (156008466 bytes), SHA-256 `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`. Both source and weights are Apache 2.0 according to the upstream LICENSE and checkpoint license statement in the official README, recorded in the research ENGINE_SETUP. The spec preserves upstream LICENSE and installed wheel licenses/notices, including Torch/CUDA notices. Existing formal face/plate model notices remain included.

## Verification record

As of 2026-11-09 20:28 local time, all 61 formal/support packages installed successfully. Metadata verified PyInstaller 6.22.3, hooks-contrib 2026.9, CPU ORT 1.23.2, PyAV 16.0.1, NumPy 2.4.6, hydra-core 1.3.2, OmegaConf 2.3.0, iopath 0.1.10, huggingface-hub 2.4.0. Initial official CUDA Torch transfer through the configured local proxy advanced slowly; cumulative installer writes increased from 848563811 to 951684049 bytes between 20:25 and 20:27:46. After bounded direct-range speed tests, the parent authorized stopping that owned installer and downloading the same official wheel in two resumable direct HTTP ranges. The official index SHA-256 is `f3af23387ac106b5b01dbef0eb021883e0c00ff4073477b7ce1cbade5ef5038d`; exact merged bytes and digest must match before installation. At 91 seconds the direct downloader had received 941621248 compressed bytes (~10 MB/s combined). SAM2 editable installation completed successfully with `SAM2_BUILD_CUDA=0`. Exact official wheel sizes are recorded above. Source freeze was reconfirmed after a frontend fix. The direct download completed in 265.34 seconds; exact size 2716982502 bytes and official SHA-256 matched. Installed torch 2.7.1+cu126 and torchvision 0.22.1+cu126; CUDA runtime 12.6 detected the NVIDIA GeForce RTX 4060 Laptop GPU. Real official truck.jpg resized to 640x480, positive point (320,240), SAM2.1 tiny, float32 and four Torch CPU threads passed on both devices: CPU model load 1.539s, prediction 2.957s, selected mask 90687 pixels; CUDA model load 0.724s, prediction 1.057s, selected mask 90685 pixels. These single-image predictor timings are not end-to-end video performance or privacy quality evidence. A non-writable NumPy fixture warning occurred; no tensor writes were performed. The native Windows onedir build completed successfully in 250.64 seconds. `dist/sam-custom-trial/Inkshield/Inkshield.exe` is 40274874 bytes; SHA-256 `860b5756da1f9a8fb04892b4ec08663bc4b39979a27d09faf93f95417ada953b`. `uv pip check` passed all 67 installed packages. Evidence is recorded in `build/sam-predictor-smoke.json` and `build/sam-environment.freeze.txt`. Fixture original SHA-256: `941715e721c8864324a1425b445ea4dde0498b995c45ddce0141a58971c6ff99`. Build warnings concerned optional TensorBoard, PyCParser generated tables, tzdata, Unix libgomp, and Torch distributed deprecations; these do not block the requested eager CPU/CUDA inference paths. The full static warning inventory remains at `build/sam-custom-trial/inkshield-sam/warn-inkshield-sam.txt`. Frozen-app acceptance is pending and belongs in the final integration report. Build success and unfrozen predictor smoke alone do not demonstrate frozen video inference, segmentation accuracy or privacy effectiveness.
