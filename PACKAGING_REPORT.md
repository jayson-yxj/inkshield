# Inkshield Windows packaging inventory

Target: Windows x64, CPython 3.11.16, PyInstaller 6.22.3 / hooks-contrib 2026.9. Single windowed Inkshield.exe; desktop.py entry point. This report records installed metadata and existing model provenance, not a legal clearance opinion.

## Contents and reproducibility

The spec allowlists index.html and precisely three ONNX files (SCRFD det_500m, MobileFaceNet w600k_mbf, HyperLPR plate), their FACE_SOURCE.md / SOURCE.md / HYPERLPR_SOURCE.md provenance, this report and the exact environment lock. This local research build includes noncommercial-research InsightFace weights and is not cleared for public/commercial distribution. Runtime uploads/exports, research, sample media, tests and face_landmarker.task are excluded. Python import dependencies and necessary package resources are discovered by PyInstaller hooks. requirements-packaging.lock.txt records the complete existing venv, not a minimal runtime dependency declaration. PACKAGING_DEPENDENCIES.json gives the full installed metadata/license-file inventory.

PyInstaller and pywebview plus their missing dependencies were installed additively. Existing production packages were not upgraded. The build script never installs or upgrades packages. Run .\build_exe.ps1 in PowerShell using the existing venv. Optional -Clean clears PyInstaller's build cache. Default output: dist/人物打码试用版/Inkshield.exe (separate build/work paths preserve prior releases). No UPX, signing, auto-download or external runtime folder is configured.

## Runtime DLLs and host prerequisites

CPU ONNX Runtime 1.23.2: collect onnxruntime.dll, onnxruntime_providers_shared.dll and its pybind extension. OpenCV headless 5.0.0.93: retain opencv_videoio_ffmpeg500_64.dll for video decode/encode; bundled upstream FFmpeg notices must accompany redistribution. NumPy native libraries and the CPython DLL are hook-collected. The spec explicitly pins the consistent Microsoft Visual C++ runtime family from Windows System32 (vcruntime140, vcruntime140_1, msvcp140, msvcp140_1, msvcp140_2, concrt140), sanitizes analysis PATH, and rejects any Conda-sourced native binary. Initial frozen startup failed because ambient PATH caused PyInstaller to bundle Anaconda MSVC 14.27.29016; current System32 runtime is 14.51.36231. The corrected bundle uses the current Microsoft files. A successful local build does not establish a clean Windows machine acceptance result.

Native pywebview uses Edge WebView2 with Python.NET/.NET Framework. Hooks include webview/lib managed assemblies and native WebView2Loader.dll, pythonnet/runtime/Python.Runtime.dll, clr_loader/ffi/dlls and cffi. The installed WebView2 browser runtime is a host prerequisite, not embedded. Desktop provides a tkinter/default-browser fallback; Tcl/Tk hook assets are included. Standard Windows system DLLs and .NET Framework are supplied by Windows. WebView2 runtime installer and Visual C++ redistributable installer are not bundled. One-file startup extracts bundled resources into a temporary PyInstaller directory; user data belongs in the launcher-configured persistent data directory.

## Optional audio export

PyAV 16.0.1 is bundled with its wheel-vendored shared FFmpeg DLLs. avcodec/avformat/avutil native license APIs report LGPL version 3 or later; PyAV wrapper BSD notices are copied. See AUDIO_DEPENDENCIES.md for versions, source/build links, trim/sample behavior and unresolved third-party corresponding-source/notice obligations. The wheel also contains x264/x265 DLLs; LGPL core strings do not establish the licenses of every codec dependency. Official LGPLv3/GPLv3 license texts accompany the portable ZIP, without claiming that notices alone fulfill redistribution obligations. Public/commercial distribution still requires the separate audit.

imageio-ffmpeg 0.6.0 is installed only for development fixture generation. Its GPLv3 FFmpeg executable is excluded from runtime via the spec; package metadata/notices can still appear in the conservative installed-environment inventory.

## Model provenance and redistribution limits

SCRFD det_500m SHA256 5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a and MobileFaceNet w600k_mbf SHA256 9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f: official InsightFace buffalo_sc weights, restricted to noncommercial research. Bundled SCRFD source is MIT; preserve FACE_SOURCE.md and the original license. Previous DEIMv2 weights are excluded from this build.

HyperLPR detector SHA256 2a985dc63a5cc947ec36d18503d6fc0fd54525b9dba17f2fe29a71e86b44456d: sourced from a third-party mirror. The HyperLPR3 package declares Apache-2.0, but original-author weight hash equivalence, standalone weight license, training data and redistribution/commercial clearance remain unverified. Preserve models/HYPERLPR_SOURCE.md in full. No research sample image is bundled.

## Installed package license inventory

The spec copies available LICENSE/LICENCE/COPYING/NOTICE files and licenses directories verbatim into third_party_licenses/<distribution>/..., including nested NumPy, OpenCV and pywebview notices. Some distributions contain no license file; metadata is only a declaration. Inventory includes build-only tools (PyInstaller is GPL with bootloader exception) and incidental pre-existing packages even when not runtime-bundled. This conservative notice bundle is not an assertion that every installed package is used at runtime. CPython's standard LICENSE.txt is explicitly collected from the build interpreter when available.

| Distribution | Version | Metadata license | Notice files found |
|---|---|---|---|
| altgraph | 0.17.5 | OSI Approved :: MIT License | 1 |
| annotated-doc | 0.0.5 | MIT | 1 |
| annotated-types | 0.8.0 | MIT | 1 |
| anyio | 4.16.0 | MIT | 1 |
| bottle | 0.13.4 | OSI Approved :: MIT License | 1 |
| certifi | 2026.10.23 | OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) | 1 |
| cffi | 2.1.1 | MIT-0 | 1 |
| click | 8.5.0 | BSD-3-Clause | 1 |
| clr_loader | 0.3.1 | Not declared | 1 |
| coloredlogs | 15.0.1 | OSI Approved :: MIT License | 1 |
| fastapi | 0.162.0 | MIT | 1 |
| flatbuffers | 25.12.19 | OSI Approved :: Apache Software License | 0 |
| h11 | 0.16.0 | OSI Approved :: MIT License | 1 |
| httpcore | 1.0.9 | BSD-3-Clause | 1 |
| httpx | 0.28.1 | OSI Approved :: BSD License | 1 |
| humanfriendly | 10.0 | OSI Approved :: MIT License | 1 |
| idna | 3.20 | BSD-3-Clause | 1 |
| mpmath | 1.3.0 | OSI Approved :: BSD License | 1 |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 20 |
| onnxruntime | 1.23.2 | OSI Approved :: MIT License | 1 |
| opencv-python-headless | 5.0.0.93 | OSI Approved :: Apache Software License | 4 |
| opentelemetry-api | 1.45.2 | Apache-2.0 | 1 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | 3 |
| pefile | 2024.8.26 | MIT | 1 |
| pip | 24.0 | OSI Approved :: MIT License | 1 |
| protobuf | 4.25.9 | 3-Clause BSD License | 1 |
| proxy_tools | 0.1.0 | OSI Approved :: MIT License | 0 |
| pycparser | 3.12 | BSD-3-Clause | 1 |
| pydantic | 2.14.2 | MIT | 1 |
| pydantic_core | 2.50.2 | MIT | 1 |
| pyinstaller | 6.22.3 | OSI Approved :: GNU General Public License v2 (GPLv2) | 1 |
| pyinstaller-hooks-contrib | 2026.9 | OSI Approved :: Apache Software License, OSI Approved :: GNU General Public License v2 (GPLv2) | 1 |
| pyreadline3 | 3.5.6 | OSI Approved :: BSD License | 1 |
| python-multipart | 0.0.33 | Apache-2.0 | 1 |
| pythonnet | 3.2.1 | MIT | 2 |
| pywebview | 6.2.1 | OSI Approved :: BSD License | 1 |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | 1 |
| setuptools | 79.0.1 | Not declared | 24 |
| starlette | 1.10.0 | BSD-3-Clause | 1 |
| sympy | 1.14.0 | OSI Approved :: BSD License | 3 |
| typing-inspection | 0.4.4 | MIT | 1 |
| typing_extensions | 4.16.0 | PSF-2.0 | 1 |
| uvicorn | 0.54.0 | BSD-3-Clause | 1 |
