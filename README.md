# 隐映 / INKSHIELD

在本机运行的视频隐私编辑器：自动遮挡人脸与车牌，通过 SAM2.1 点选自定义目标，在独立图层与时间区间中编辑保护效果，预览并导出视频。

## 使用软件

Windows 用户可直接下载 [便携版 Release](https://github.com/jayson-yxj/inkshield/releases)。下载两个分卷、合并脚本及校验清单到同一目录，运行合并脚本，校验后完整解压。运行 `Inkshield/Inkshield.exe`，保留 `_internal` 和所有依赖，EXE 不能独立运行。

系统要求和操作步骤见 [用户说明](docs/user/WINDOWS使用说明.txt)。已发布的修订 2 是此前验收的冻结构建；本次源码目录重组不会替换已有二进制。

## 从哪里读起

| 想了解什么 | 入口 |
| --- | --- |
| 应用如何启动 | [包入口](src/inkshield/__main__.py) → [桌面启动器](src/inkshield/desktop.py) |
| HTTP 接口与任务如何组织 | [服务端](src/inkshield/server.py) |
| SAM 点选、预热与传播 | [SAM 服务](src/inkshield/sam_service.py) → [推理引擎](src/inkshield/sam_engine.py) |
| 多图层与效果区间 | [图层合成](src/inkshield/mask_layers.py)、[时间区间](src/inkshield/mask_timeline.py) |
| 播放和音频导出 | [保护视频](src/inkshield/preview_video.py)、[音频导出](src/inkshield/audio_export.py) |
| 编辑器交互 | [编辑器页面](src/inkshield/web/index.html)、[图层交互](src/inkshield/web/layers_ui.js)、[工作区交互](src/inkshield/web/workspace_ui.js) |
| 如何开发、测试与打包 | [文档导航](docs/README.md) |

后端按 Python 包组织；前端目前是原生 HTML/JavaScript，没有 Node 构建步骤。部分编辑器逻辑仍内嵌于页面，服务端接口集中在一个模块，可先沿上述调用关系理解，再阅读具体实现。

## 目录结构

```text
src/inkshield/          应用 Python 包
  web/                 编辑器、启动页、教程与样式
assets/                应用图标及第三方许可
models/                模型来源、许可与校验信息（不含权重）
tests/
  unit/                不依赖真实模型的单元测试
  integration/         后端及 SAM 集成测试
  ui/                  浏览器、WebView2 和几何测试
  probes/              真实设备与推理探针
tools/
  build/               构建入口
  release/             发行归档与分卷工具
  verification/        平台与冻结包验收
  benchmarks/          性能测量
  dev/                 开发辅助工具
packaging/             PyInstaller 配置、启动器及依赖清单
requirements/          依赖列表与打包锁定记录
scripts/               开发启动脚本
docs/                  开发、发行、用户说明与历史评审
```

`runtime/`、`build/`、`dist/`、`research/` 和 `evidence/` 是被忽略的本地数据及生成物，不属于克隆后的源码结构。

## 开发运行

推荐 Python 3.11。在仓库根目录创建环境并安装应用：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m inkshield --help
```

模型权重和 SAM 第三方源码不会随 Git 克隆获取，应用也不会自动下载。运行视频分析前，请依据 [模型来源](models/SOURCE.md)、[人脸模型](models/FACE_SOURCE.md)、[车牌模型](models/HYPERLPR_SOURCE.md) 及 [SAM 构建说明](docs/distribution/SAM_PACKAGING.md) 准备对应依赖。基础安装不包含完整 Torch/CUDA/SAM 环境。

准备完成后启动本地服务或桌面应用：

```powershell
.\.venv\Scripts\python.exe -m inkshield --serve-only --port 8765
# 桌面窗口需安装桌面依赖，并具备系统 WebView2
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
.\.venv\Scripts\python.exe -m inkshield
```

服务默认仅监听回环地址，视频处理在本机完成。模型数据、只读界面资源与可写运行数据的定位集中在 [路径配置](src/inkshield/app_paths.py)。

## 测试与构建

安装应用后，从仓库根运行单元测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v
```

集成、原生桌面和冻结包验收需要各自的模型、平台和素材。历史验收记录可能引用未纳入 Git 的本地夹具；这些记录不代表克隆后即可完整复现。具体条件见 [文档导航](docs/README.md)。

Windows 构建从 [SAM 构建脚本](tools/build/build_sam_exe.ps1) 和 [PyInstaller 配置](packaging/pyinstaller/inkshield-sam.spec) 开始，详细步骤见 [构建说明](docs/distribution/SAM_PACKAGING.md)。

## 功能边界

自定义传播每个片段最多 **150 帧、1280×720**，长素材需先分割。多层批量传播串行执行，失败保留已完成结果，重试只处理剩余层。预览会提示保护缺口，导出要求有效启用层完成分析。支持当前片段保留音频或静音导出，不自动合并全部片段，重启不恢复未保存编辑会话。

自动检测和追踪可能漏检或跟丢，请检查完整片段和最终导出。第三方代码与模型分别适用其许可，见 `models/` 和 `assets/licenses/`；人脸模型有非商业研究限制，车牌权重商业及独立再分发授权尚未核实。项目尚未声明统一开源许可证。
