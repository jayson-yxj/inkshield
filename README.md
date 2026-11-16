# 隐映 / INKSHIELD

本地运行的视频隐私编辑工具，支持人脸与车牌自动遮挡、SAM2.1 自定义目标、多图层编辑、批量传播及 CPU/GPU 运行。视频处理在本机完成，服务默认仅监听回环地址。

## Windows 便携版

从 [GitHub Releases](https://github.com/jayson-yxj/inkshield/releases) 查看已发布的 Windows x64 程序及下载说明。发行文件由 Release 单独提供，不纳入 Git 源码仓库。

完整解压后，在 `Inkshield` 文件夹内运行 `Inkshield.exe`。**必须保留 `_internal` 和整个目录，不能只下载或复制 EXE。** 无需安装 Python。若 Release 使用分卷，请将全部分卷、合并脚本和校验清单放到同一目录，运行合并脚本并通过 SHA-256 校验后再解压。

适用 Windows 10/11 x64，建议至少 8GB 内存及足够缓存空间；本机测试不代表其他硬件/驱动兼容性保证。桌面窗口依赖系统 WebView2。GPU 需要兼容的 NVIDIA 显卡和驱动；包内含 CUDA 运行库，无需另装 CUDA Toolkit。启动时后台优先预热可用 GPU，失败会说明原因并回退 CPU；手动指定不可用设备时会明确报错。

详细操作与环境要求见 [Windows 使用说明](WINDOWS使用说明.txt)。

## 主要功能

- 导入、逐帧定位、分割、调整切点及撤销；每个视频片段持有独立图层与分析状态。
- 自动检测人脸/头部及部分面部区域、车牌，支持人物选择、马赛克、模糊及黑色遮挡。
- 自定义模式通过包含点/排除点预览 SAM 区域，传播为逐帧遮罩。每个片段最多 **150 帧**、原始尺寸最高 **1280×720**；长素材需先分割。合法空遮罩表示该帧目标不在画面。
- 多图层与可编辑效果区间；批量传播按顺序处理有提示点且尚未就绪的自定义层，失败保留已完成结果，重试仅处理剩余层。
- 合成保护播放、面板收展、画面缩放平移及 8 章 96 秒内置教程。
- 静音或保留原音轨（转为 AAC）导出当前片段。预览会提示未保护/保护不完整；有效启用层尚未完成分析时导出拒绝执行。

请检查完整片段及最终导出；自动检测或追踪可能漏检、跟丢，处理成功不等于隐私保护已充分。程序重启不恢复未保存编辑会话，当前不自动合并全部片段。

## 源码开发

推荐 Python 3.11，独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe desktop.py
```

模型权重、SAM 第三方源码和环境不会随 Git 克隆获取，应用也不会自动联网下载模型。请先依据 [模型来源](models/SOURCE.md)、[人脸模型](models/FACE_SOURCE.md)、[车牌模型](models/HYPERLPR_SOURCE.md)、[SAM2.1 来源](models/SAM21_SOURCE.md) 及 [SAM 构建说明](SAM_PACKAGING.md) 准备并校验依赖。SAM 构建环境使用额外的 Torch/CUDA 与 SAM2 依赖，基础 requirements 不是完整的 SAM 构建环境。

运行不依赖模型的合成帧单元测试：

```powershell
.\.venv\Scripts\python.exe -m unittest test_mask_layers test_mask_timeline test_preview_video
```

真实模型、桌面和冻结包验收需要对应本地模型、Windows 环境、测试素材及既有证据。历史 `research/`、`evidence/`、`runtime/` 内容属于本地工作记录，不在仓库内；引用它们的验收脚本不能仅靠克隆直接复现。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| 根目录 Python、HTML、JS、CSS | 生产后端、桌面入口与前端；保留路径以兼容资源加载和已验证打包入口 |
| `tests/`、根目录 `test_*` / `verify_*` | 单元测试、集成与平台验收入口 |
| `build_*.ps1`、`*.spec`、`package_*`、`prepare_release_assets.py` | 构建、依赖收集、归档校验和 Release 分卷工具 |
| `assets/` | 图标和第三方许可 |
| `models/` | 模型来源、许可及校验信息；不包含权重 |
| [docs/](docs/README.md) | 结构说明及历史评审报告 |
| `research/`、`evidence/`、`runtime/`、`build/`、`dist/` | 本地研究、录制、用户数据、缓存和生成物，全部忽略 |

构建使用根目录 [build_sam_exe.ps1](build_sam_exe.ps1) 与 [inkshield-sam.spec](inkshield-sam.spec)。构建所需的说明及依赖清单暂保留根目录，避免改变包内资源契约。

## 许可与发行边界

模型和第三方组件拥有各自许可，详见 `models/` 来源文件及 `assets/licenses/`。原有人脸模型存在非商业研究限制，车牌权重的独立再分发/商业授权尚未核实；本地试用产物不代表已取得商业分发授权。项目暂未声明统一的开源许可证，请勿将源码可见理解为全部代码、模型与二进制均可任意再分发。
