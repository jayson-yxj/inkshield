# 文档导航

- [开发架构与贡献路线](development/architecture.md)：模块职责、数据流和修改入口。
- [测试入口](../tests/README.md)：常规回归、原生界面验收与本地历史探针的区别。
- [Windows 使用说明](user/WINDOWS使用说明.txt)：便携版启动、工作区、数据目录与限制。
- [SAM 构建说明](distribution/SAM_PACKAGING.md)、[基础构建报告](distribution/PACKAGING_REPORT.md)、[音轨依赖](distribution/AUDIO_DEPENDENCIES.md)：构建环境与分发依赖记录。
- [依赖清单](../packaging/PACKAGING_DEPENDENCIES.json)：历史构建环境的完整元数据与许可文件清单。
- [修订2发布记录](reviews/SAM_RELEASE_20261110.md)、[教程与发布验证汇总](reviews/RELEASE_20261110_REVIEW.md)：历史冻结产物的验收范围。

文档按 development（开发）、distribution（构建与分发）、user（使用）、reviews（阶段评审）分类。生产代码位于 `src/inkshield`，前端位于其 `web` 子目录；工具按职责放在 `tools`，PyInstaller spec 位于 `packaging/pyinstaller`。

reviews 中的历史路径、时间和哈希保留当时记录，不直接当作当前运行命令。research、evidence、runtime、模型权重、视频、虚拟环境与打包结果不随 Git 克隆发布；历史冻结结论不能替代当前版本重新验证。当前命令均从仓库根执行。
