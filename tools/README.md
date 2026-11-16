# 工具导航

这些目录存放开发和交付工具，生产应用位于 `src/inkshield`。命令从仓库根执行；先安装 editable 应用，避免依赖当前工作目录或裸模块导入。

| 目录 | 用途 | 起点 |
| --- | --- | --- |
| build | Windows 原生构建、构建编排 | [SAM 构建](build/build_sam_exe.ps1)、[基础构建](build/build_exe.ps1) |
| release | 验收编排、归档、分卷 | [发行验收编排](release/accept_verified_release.py)、[归档](release/package_sam_release.py)、[分卷](release/prepare_release_assets.py) |
| verification | API、桌面及冻结产物验收 | [适用条件](verification/README.md) |
| benchmarks | 推理和分辨率性能测量 | [推理基准](benchmarks/benchmark_inference.py) |
| dev | 图标生成与历史界面辅助 | [图标工具](dev/create_icon.py) |

日常修改先执行 [测试套件](../tests/README.md)，再按实际改动选择平台验收。这里的真实模型、GPU、桌面和发行脚本有额外依赖，不属于全部可在新克隆上直接运行的单元测试。

PyInstaller 配置位于 [打包目录](../packaging/pyinstaller/)，依赖和步骤见 [构建文档](../docs/distribution/SAM_PACKAGING.md)。旧冻结包与历史证据保留；目录重组后的新发行必须重新冻结源码并重新验收。
