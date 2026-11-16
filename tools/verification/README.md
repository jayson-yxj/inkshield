# Verification tools

当前推荐的源码回归入口（从仓库根目录运行）：

```powershell
python -m pip install -e .
python -m unittest discover -s tests/unit -p 'test_*.py'
python -m unittest discover -s tests/integration -p 'test_*.py'
node tests/ui/workspace_ui_geometry.cjs
```

原生 UI、模型推理、GPU 和冻结产物验收需要对应依赖、模型、视频夹具及 Windows 桌面；这些条件不由源码单测证明。具体测试说明见仓库 tests 与 docs。

本目录保留历次 API、UI、模型与发布验证脚本。所有路径已适配 `src/inkshield`；保留脚本不代表旧验证契约已经适配当前产品。已实测的历史不兼容：

- `verify_segments.py` 的假检测器仍返回 tuple，当前后端要求带 `det_score` 的人脸对象；版本断言仍为 0.10.0，当前为 0.11.0。
- `verify_layout_ui.js`、`verify_timeline_ui.js`、`verify_continuous_ui.js` 复用的历史 DOM mock 缺少 `document.documentElement.dataset`，无法运行当前界面。
- 一些模型/API 验证依赖本地 runtime 视频或旧缓存；`verify_face_release.py`、`verify_sam_legacy_release.py` 还调用未纳入版本控制的历史 `runtime/verify_frozen_audio.py`，不属于 clone 后即用的回归链。

发布入口在 `tools/build/build_verified_release.py` 和 `tools/release/accept_verified_release.py`。新布局必须重新冻结并人工审查 `runtime/release-source-freeze.json`，键为仓库相对的新路径；旧 `release-20261110-source-freeze.json` 与旧 dist 产物保持历史证据，不可自动沿用。HTTP 路由资源名与源码 `src/inkshield/web`、冻结包 `_internal/web` 物理位置分别核对。当前未重建 Windows 产物，也未声称新 release binding 通过。
