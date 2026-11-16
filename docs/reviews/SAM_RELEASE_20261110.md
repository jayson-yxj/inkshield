# 2026-11-10 多层工作区 Windows 修订2验收

当前状态：修订2构建、CPU/CUDA接口（含保护视频编码/解码）、旧功能、正式EXE桌面启动退出及包内教程36/36已通过。完整原生矩阵及最终ZIP归档均已通过。归档 `dist/inkshield-20261110-r2/隐映-Windows-x64-多层工作区CPU-GPU版-20261110-修订2.zip` 共2,952,389,956字节，4092个成员；SHA256 `f7cc17d4a61400fe1cd0daa72ccc7d0916d5c35df79635ecc7f5f5e1c46b1335`。压缩前清单文件大小合计4,711,218,857字节（不含清单自身）。CRC、精确成员集合、逐文件大小/SHA256、嵌入清单哈希及打包后构建绑定全部通过，归档job exit0已收取。归档证据为 `runtime/sam-release-package-20261110.json`。最终原生矩阵 `runtime/sam-frozen-matrix-20261110-145004-a50e8691/evidence.json` status=passed，绑定同一r2 EXE；严格复用同r2 CPU/CUDA证据，真实OS原生27项通过，7次焦点检查目标HWND均匹配，browser_errors=[]，包内教程再次36/36通过，全部自有PID与端口清理通过。

## 当前构建

目录 `dist/inkshield-20261110-r2/Inkshield`；EXE SHA256 `40fff8f5d637f75f978aca207384e6204a9a4d54310f9637c0e4784c6821fdef`。冻结生产源码未变，教程SHA256 `4a126acb96994aafa8d64ccc037d66de996f435384c7cd857ceb31bd8e887592`，8章96秒。构建绑定见包内BUILD_PROVENANCE.json及runtime/release-20261110-source-freeze.json。

首版构建009943394e3fa570c304568c92dea7ae853d452e1a9308638ed1528c29c41d14的保护播放失败 `No module named 'imageio_ffmpeg'`。修订2移除spec旧exclude，收集imageio_ffmpeg与其wheel FFmpeg程序。首版证据不用于认证修订2。

## 修订2证据

- CPU/CUDA成功：`runtime/sam-frozen-matrix-20261110-142853-f039f849/evidence.json`。两项包含真实保护视频生成、H264/yuv420p、帧数/尺寸/fps、遮罩像素与音轨/AAC解码检查；该矩阵整体因后述旧撤销断言失败，不能称整体通过。
- 旧功能：`runtime/sam-legacy-aee60f33b5/acceptance.json`，人脸身份、车牌、音频均true；同目录cleanup.json三项true。
- 桌面：`runtime/sam-desktop-launch-20261110-144546-616e96aa/evidence.json`，正式EXE WebView2启动、WM_CLOSE正常退出及4项清理通过。
- 包内教程：`runtime/sam-tutorial-2639c1a213/evidence.json`，36/36、6份HTTP资源绑定及4项清理通过。此为DOM驱动WebView2功能验证，非OS点选或人工视觉审查。

## 撤销分割诊断与测试契约修正

`runtime/sam-dom-undo-1ab4881a67/diagnostic/evidence.json:406-551`提供明确expected/actual差异：恢复后segments=1，settings和analysisId完全一致，analysisReady=true，活动layer-1及分析绑定一致；仅 `playbackSame=false`，因为原始playback=null，恢复后为同analysisId的真实5帧1280×720、25fps、custom CUDA元数据。其custom_mask_url含原分析ID。

index.html的selectSegment在ready&&!playback时自动loadPlayback；恢复null后加载元数据是正常懒加载，不是丢失恢复结果。测试改为保留完整settings、analysisId、图层持久状态、活动层和范围严格相等；缓存必须与该分析真实元数据一致且与活动图层绑定，继续执行真实播放/暂停后点选失效检查。状态文字和派生playback对象允许正常刷新，不把null引用恒等当业务契约。

上述诊断通过DOM点击及直接moveCut触发真实冻结应用，包含真实推理、播放与音/静音导出，但明确不替代OS点击矩阵。修正后DOM复验 `runtime/sam-dom-undo-3f1819fd1b/diagnostic/evidence.json` 通过；两轮诊断runner各四项清理true。随后正式OS矩阵145004-a50e8691通过，真实鼠标点选和拖动、撤销恢复、保护视频播放、暂停后点选失效均正常。未改生产代码。

## 历史焦点问题

此前多次前台请求失败及600秒用户激活超时，均清理自有窗口、服务和端口；只读发现前台标题微信不证明微信抢占原因。之后用户激活窗口已成功执行真实OS点选/传播及修订2保护视频呈现。原生测试仍保留真实OS点击、保护视频呈现和最终导出要求，不降低发布门禁。

## 边界

仅本机Windows/RTX4060 Laptop GPU验证，不等于无NVIDIA机器/其他驱动跨机实测。教程减少动态偏好为模拟，未做截图人工视觉审查。模型和第三方权重授权边界见使用说明。现有50164服务、旧交付包均保留。
