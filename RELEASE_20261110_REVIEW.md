# 隐映 2026-11-10 教程更新与便携包发行

状态：修订2全部功能验收及ZIP归档校验通过，已完成交付准备。用户授权先更新教程，再打包Windows CPU/GPU便携版。现有50164服务及旧发行包保留。

## 最终构建与范围

构建目录：dist/inkshield-20261110-r2/Inkshield。
EXE SHA256：40fff8f5d637f75f978aca207384e6204a9a4d54310f9637c0e4784c6821fdef。
12项源码冻结：runtime/release-20261110-source-freeze.json；构建证明：包内BUILD_PROVENANCE.json。

包含独立多图层、效果轨道、待分析层预览状态、统一编辑工具栏、自动/自定义主题、工作区收展，以及同片段自定义图层串行批量传播、失败保留结果和剩余层重试。构建补齐layers_ui.js、workspace_ui.js、workspace_ui.css及相关后端模块；修订2补齐imageio_ffmpeg与FFmpeg编码程序。

## 教程

教程03为8章96秒，示例1280×720、25FPS、125帧；涵盖导入分段、独立图层、选点、批量传播与失败重试、统一编辑、视图整理及保护状态/严格导出。保留连续鼠标轨迹、动态速度、点击反馈和章节播放控制。
教程SHA256：4a126acb96994aafa8d64ccc037d66de996f435384c7cd857ceb31bd8e887592。
源码教程WebView2验收36/36，769个采样帧，源码测试前后一致；1ms采样最大位移1.4985像素、章节边界0.67265像素、点击偏差0。证据evidence/tutorial-v03/native-results.json。
修订2独立包内教程36/36：runtime/sam-tutorial-2639c1a213/evidence.json；最终矩阵再次验证包内教程36/36。

## 修订2功能验收

- 最终矩阵runtime/sam-frozen-matrix-20261110-145004-a50e8691/evidence.json状态passed，绑定修订2实际路径、EXE、冻结资源和构建证明。
- CPU/CUDA API通过，包含真实保护视频H264/yuv420p编码解码、帧数/尺寸/fps、保护像素与AAC音轨；严格复用同一修订2构建的runtime/sam-frozen-matrix-20261110-142853-f039f849/evidence.json中的成功接口证据。
- 真实OS原生交互27项通过，包括点选、传播、保护视频实际呈现帧、带音/静音导出、分割移动撤销与后续播放点选；browser_errors=[]。7次焦点事件均验证目标为前台，cuda-native四项进程/端口清理均true。
- 旧功能：runtime/sam-legacy-aee60f33b5/acceptance.json及cleanup.json，人脸身份、车牌与音轨通过。
- 实际EXE桌面启动与正常关闭：runtime/sam-desktop-launch-20261110-144546-616e96aa/evidence.json，通过且清理完成。

## 源码回归

六组VM测试通过：批量传播、null阈值、图层状态、播放错误、最终选帧和原始视频滑杆。统一工具栏12/12、分割合并图层回归通过。Python test_mask_layers、test_mask_timeline、test_preview_video共20/20通过。

## 修复及证据边界

首版包真实保护播放发现No module named 'imageio_ffmpeg'；修订2修正spec排除项、收集模块与编码二进制并重新构建验收。首版通过结果不充当修订2通过依据。
撤销分割旧断言要求playback严格等于原来的null；定向诊断证实settings、analysisId、活动图层及范围均恢复，playback合法懒加载为同analysisId的5帧1280×720/25fps/custom cuda元数据。证据runtime/sam-dom-undo-1ab4881a67/diagnostic/evidence.json:406-551。修正测试为业务状态、图层持久状态及同分析元数据/缓存绑定；DOM复验runtime/sam-dom-undo-3f1819fd1b/diagnostic/evidence.json通过，随后完整OS矩阵亦通过。未因此修改冻结生产源码。

教程DOM测试、减少动态偏好模拟与实际OS鼠标交互分别举证；未进行截图人工视觉审查或其他硬件/驱动跨机验证。本机为Windows、RTX 4060 Laptop GPU。

## 归档

归档拒绝覆盖旧ZIP；核验CRC、完整成员集合、逐项大小、流式SHA256和内嵌SHA256.json清单。清单不包含自身摘要。归档已成功，后台任务exit0且结果已收取。最终ZIP：dist/inkshield-20261110-r2/隐映-Windows-x64-多层工作区CPU-GPU版-20261110-修订2.zip；大小2,952,389,956字节，4,092个成员，清单自身外文件解压合计4,711,218,857字节。整体SHA256：f7cc17d4a61400fe1cd0daa72ccc7d0916d5c35df79635ecc7f5f5e1c46b1335。上述CRC、成员集合、逐文件大小/哈希、清单及最终release_binding全部通过。记录runtime/sam-release-package-20261110.json绑定本次成功矩阵、旧功能及桌面验收。全部自有测试任务收取并清理，原50164服务HTTP200，旧包保留。
