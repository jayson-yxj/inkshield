# 架构与贡献路线

先读仓库 README 和本文，再按要修改的行为进入模块。源码使用 `src` 布局，统一通过 `inkshield.*` 导入；安装项目或设置 `PYTHONPATH=src` 后即可在仓库根运行。

## 从桌面入口到导出

`inkshield.desktop` 启动本机 FastAPI 服务与 WebView2 窗口；`app_paths` 负责源码/打包资源和用户数据目录。`server` 定义 HTTP 路由、上传媒体、分析结果、任务状态、并发配额以及预览和导出编排。

浏览器读取 `web/index.html`。`layers_ui.js` 管理图层交互，`workspace_ui.js` 与 `workspace_ui.css` 管理面板、画面缩放和平移；教程与启动预览也是 web 下的静态资源。前端以 media_id、analysis_id、job_id 引用服务端对象，不能将浏览器选中状态当作服务端分析完成的依据。

```text
视频导入 → MEDIA 元数据 → 自动分析 / SAM 提示与传播
                            ↓
                        ANALYSES 缓存
                            ↓
          图层 + 时间区间 + 样式配置快照
                     ↙              ↘
                单帧预览       连续保护播放 / 导出
                                      ↓
                               视频编码 + 音轨处理
```

## 后端模块边界

| 模块 | 职责 |
| --- | --- |
| server | API、媒体和任务生命周期、分析结果与导出编排 |
| face_detector、scrfd、identity_gallery | 人脸检测/对齐、特征与人物确认；模型文件保留在 models |
| plate_detector | 车牌检测与检测结果适配 |
| masking | 根据已缓存检测框应用遮罩样式 |
| sam_engine | SAM 模型加载、设备能力、点选特征缓存与双向视频传播 |
| sam_service | HTTP 参数与形状校验、推理锁、预热、磁盘遮罩存储与发布 |
| mask_timeline | 效果区间的规范化、边界与配置快照 |
| mask_layers | 同媒体多分析结果的有序合成与一致性校验 |
| preview_video | 浏览器可播放视频编码、缓存及连续预览任务 |
| audio_export | 原音轨裁剪、重采样、AAC 编码和封装 |
| cpu_runtime、app_paths | CPU 运行配置与资源/用户数据定位 |

改变样式时优先复用分析缓存；缺失遮罩与合法空遮罩具有不同含义。SAM 传播要覆盖整个请求区间，失败不得发布不完整分析。任务响应与前端对象身份绑定，图层合成顺序和时间区间采用明确快照，避免异步结果污染新编辑状态。

## 修改与验证

- 遮罩、区间或连续预览：读对应模块与 `tests/unit`，执行 `python -m unittest discover -s tests/unit -v`。
- 人物选择、SAM API、传播和预热：读 `tests/integration`，执行 `python -m unittest discover -s tests/integration -v`；这些合同测试模拟模型推理。
- 缩放、平移与布局：读 web 资源和 `tests/ui`，先运行 `node tests/ui/workspace_ui_geometry.cjs`，原生验证另外需要 Windows WebView2。
- 构建与发布：入口按职责位于 `tools/build`、`tools/release`、`tools/verification`，spec 位于 `packaging/pyinstaller`；参考 distribution 文档。
- 性能与开发辅助：查看 `tools/benchmarks`、`tools/dev`，不要把本地研究权重或生成结果提交进仓库。

测试条件与历史探针限制详见 [测试说明](../../tests/README.md)。修复应同时核对包导入、mock 字符串、资源路径及脚本的仓库根计算；不要依赖运行时恰好处在源码目录。历史报告位于 reviews，不能将旧产物验收迁移为新版本完成证明。
