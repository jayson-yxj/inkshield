# 隐映教程 03 原生验收

交付源码：`D:\财富密码\face-mosaic-prototype\tutorial-preview.html`

SHA-256：`4a126acb96994aafa8d64ccc037d66de996f435384c7cd857ceb31bd8e887592`

教程为 8 章 / 96 秒，模拟素材 1280×720、25 FPS、5 秒（125 帧），先定位分割再处理。包含独立图层、当前层自动/自定义切换、衣物与车牌逐层选点、串行批量传播、失败保留与重试、统一编辑工具栏、面板收展、缩放平移、预览保护状态和严格导出。保持全局连续鼠标曲线、加减速、拖尾、按压缩放和点击涟漪。处理耗时压缩，画面明确标记为模拟演示。

## 验收结果

`tests/tutorial_v03_webview.py` 在现有 `http://127.0.0.1:50164/` 服务真实打开教程 dialog / 同源 `/tutorial` iframe，使用 pywebview 的 edgechromium（WebView2）后端。

最终源码原生验收 **36/36 PASS**，源码测试前后 SHA-256 一致。结果详见 `native-results.json`。本次运行窗口 1440×1000，iframe 实测高度 790 CSS px。

- 8 个章节导航、96 秒终点、播放到终点后重启、暂停保持、range input 定位、重播、真实 requestAnimationFrame 推进。
- 769 个采样帧（每 0.125 秒）全部绘制；该阶段错误事件为 0。
- 1 ms 鼠标采样最大位移 1.498493570463458 canvas px；章节边界 ±1 ms 最大位移 0.6726490600691546 px。
- 关键点速度差估计最大 0.07742759274791935 px/s；点击坐标与鼠标误差 0。
- 初始批次第一层 ready 时 50%，失败停在 75%；重试单层队列从 0%→100%，已完成层保持。
- 衣物正点和第三层效果选择锚点、失败关闭后重试路径。
- 空提示层被跳过但仍阻止导出，删除不用的层后示范导出。
- iframe 内章节按钮可滚动到达（底部 789.3000 <= iframe 790），关闭移除 src 并回焦教程入口，重开使用新文档。
- 新原生 iframe 内预置 matchMedia 的 reduced-motion 返回值后，源码初始化暂停。

生成了 `batch-frame.png`（46 秒 canvas），但模型图像读取能力不可用，未做截图视觉审查。

## 复用测试

默认：

```powershell
& 'D:\财富密码\face-mosaic-prototype\.venv\Scripts\python.exe' 'D:\财富密码\face-mosaic-prototype\tests\tutorial_v03_webview.py'
```

包内服务可指定 `--url http://127.0.0.1:PORT/ --source '包内实际tutorial-preview.html路径' --output '独立证据目录'`。参数入口在36项原生检查完成后新增；核心检查与冻结教程未变。测试只创建并关闭自己的 WebView2 窗口，不启动/停止现有服务。运行完需核查 JSON 中 url、source 哈希和通过数；source 哈希是提供的本地文件，不代替服务响应身份验证。

## 结论边界

这是教学画布及真实编辑器教程弹窗集成验收，动画播放用加速采样并短时间观察真实 RAF，不是 96 秒全时录屏审查。按钮由 DOM click/input 驱动，不是操作系统鼠标注入。reduced-motion 使用模拟偏好，并未更改或验证 Windows 系统设置。未验证模型推理质量、实际导出编码、打包产物或所有屏幕尺寸；生产编辑器文件与打包脚本未修改，50164 服务保持运行。
