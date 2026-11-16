# 测试入口

从仓库根运行，先安装项目开发环境（`python -m pip install -e .`），或设置 `PYTHONPATH=src`。不要把 `src/inkshield` 加入搜索路径：生产模块统一通过 `inkshield.*` 导入，mock 也使用同一模块身份。

| 目录 | 范围 | 克隆后条件 |
| --- | --- | --- |
| unit | mask_layers、mask_timeline、preview_video | 安装基础依赖与 imageio-ffmpeg；生成临时视频，不需要模型或历史证据 |
| integration | 人脸后端、SAM HTTP、传播、预热合同 | 基础依赖；模拟推理器，不需要 torch、CUDA 或模型权重 |
| ui | JS 几何与独立/服务 WebView 验证 | 几何需要 Node.js；原生窗口需要 Windows、pywebview、WebView2 |
| probes | 真实 GPU 和历史用户素材探针 | 本地历史工具；需要未随克隆提供的 vendor、模型、CUDA、素材或先前生成帧 |

```powershell
python -m unittest discover -s tests/unit -v
python -m unittest discover -s tests/integration -v
python -m unittest discover -s tests -t . -v
node tests/ui/workspace_ui_geometry.cjs
python tests/ui/workspace_ui_webview.py
```

unit 名称表示此处的功能模块回归层；其中包含真实 H264/AAC 编码和 HTTP 合同，执行时间长于纯函数测试。`test_mask_layers` 复用 preview 套件，因此发现数包含继承的用例。

`tests/ui/tutorial_v03_webview.py` 默认连接历史本地服务 `http://127.0.0.1:50164/`，可以用 `--url`、`--source`、`--output` 指定当前目标；它不会启动服务。默认历史输出位于本地忽略的 evidence。运行前应指定新的输出目录，历史冻结结果不自动沿用于当前源码。

probes 不由 unittest 自动收集。`sam_middle_anchor_gpu_probe.py` 生成合成帧，但仍依赖本地 `research/sam21-prototype/vendor/sam2` 与模型权重；`sam_real_middle_anchor_gpu_probe.py` 还使用历史绝对素材路径和已提取帧。它们用于追溯实验方法，不能宣称新克隆即能重现 GPU、桌面或视觉验收。旧 dist/runtime/research/evidence 保持原样。
