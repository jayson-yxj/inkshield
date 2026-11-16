# 预览连续播放、统一编辑工具和主题更新

当前状态：最终冻结源码实际WebView2完整验收54/54通过，浏览器错误0，10个源码哈希前后一致。原片/混合图层跨片段自然结束和重播、滑块帧同步均通过。50164在线四个前端资源与冻结源码一致，已完成WEB交付准备。

用户范围：未分析图层不应阻断连续预览；主题过渡更平滑，导入视频按钮跟随模式颜色；视频与效果共用编辑按钮；说明并改善工作区收起入口。仅更新50164网页，不打包，不重启后端。

契约：预览合成已就绪的有效图层，未就绪图层明确提示；无就绪效果时可播放原片。导出保持完整分析校验。真正的网络、解码或编码失败仍明确报错。当前活动图层未就绪时，也必须保留其他就绪图层的预览效果。

统一编辑入口：splitTimelineSelection / deleteTimelineSelection 按选择对象路由；splitVideoSelection 由多层实现覆盖。界面只显示一套分割/删除/撤销，兼容隐藏旧效果按钮。工作区视图工具独立保留。

已复跑通过：test-layer-state.cjs、test-layer-playback-errors.cjs、test-layer-pending-preview.cjs；项目内evidence/unified-toolbar-vm.cjs（12/12）与runtime/test_split_layers.cjs。新版pending预览允许子集，strict导出拒绝未分析，错误与异步取消归属测试均保留。

主题使用9个注册的可继承颜色变量，在root上420ms插值，使切换中重建的节点也继承中间色。独立WebView2覆盖重建节点、快速反转、导入按钮及面板收起恢复；最终实际页面主题中间色、重建节点、导入按钮和面板几何/状态验收通过。

补充回归：test-layer-disclosure.cjs通过缓存预览和拖动预览完成后的状态提示恢复，以及旧选择/播放中的异步归属约束。50164实际HTTP页面与三个前端资源均和工作区逐字节哈希一致，无需重启。

冻结前端：index.html `9b65673074d99879ba2d3c0ed5acd2c22572157ecf6924b1bea32a39fe4aa894`；layers_ui.js `c6d21dada466498e5c4d25e13dbe39e89f64eabc3dc15a3cb8d881a5d1c86287`；workspace_ui.css `bdcdd2f94b943347bac4186dcd2510e8f0fd44bd920ad4bb563e9b07faf6085a`；workspace_ui.js `02a54392cdc2bd14e5943fefc0748af13e8a6f356a32ecc48eabbd9bc04efdc2`。

原生验收第一版52/52通过，浏览器错误0、10个源码哈希前后相同。覆盖主题中间色、三面板收起恢复、共享工具栏操作与撤销、全未分析及部分分析的140+10帧跨片段播放和重播。固定帧已分析自动层相对原片ROI MAE为45.41，确认活动的未分析自定义层不会丢失已就绪层效果。

追加发现并修复：全未分析时滑块改变source.currentTime但globalFrame未同步，连续播放起点错误。schedulePreview入口现在调用updateFrameLabel，统一同步局部帧、全局播放头和工具状态；不修改samDisplayed等解码证据。test-layer-raw-slider-readonly.cjs已转为生产修复回归并通过，其他四组图层回归全部通过。修后50164四个前端HTTP资源再次逐字节哈希一致。

修后额外原片滑块0断言通过，但随后连续播放出现30秒定位超时；启动前及前1.2秒原视频均为currentTime=0、seeking=true、readyState=1，token/generation稳定，90秒后仍未解码。证据保存在native-report-postfix-startup-diagnostics.json。代码确认input/change各发起一次相同目标currentTime赋值；候选已改为目标时间差大于1e-5才写入，同目标复用在途定位。setter计数回归确认input/change只写一次、新目标仍可定位，5组图层回归通过；但c6d21d候选原生复测仍在同处超时（33项已执行检查通过、0浏览器错误），因此去重没有解决实际卡住，正在追加媒体状态与事件诊断；网络Range与浏览器内部原因未记录，不能据此断言。进一步诊断native-report-media-play-probe.json确认：选择片段时base selectSegment先按保存帧定位0，timeline wrapper再按全局播放头定位5.56秒，滑块输入接着定位0，三次发生在3.5毫秒内，之后无seeked。全部发生在可见视频上，blob已完整缓冲[0,6]、networkState=1且无媒体error；诊断额外play未恢复，也无后续异步定位writer。已修复base选择函数直接使用最终局部帧（第三参localFrame=null），timeline wrapper传入desired-seg.start并取消重复预览。实际base+wrapper函数回归test-select-final-frame.cjs验证同片段保存、跨片段、首尾clamp、第0帧和busy路径均只提交一次最终帧；五组图层回归、共享工具12/12与拆分合并回归均通过，最终完整WebView2复测54/54通过，包含原片滑块0及合成预览25→0同步、全待分析和混合图层跨两段自然结束与重播；无诊断play介入。native-report-final-pass.json及native-report.json记录同一最终全量结果：浏览器错误0，10个源码哈希前后一致，ROI MAE45.41；reduced-motion模拟下图标/预览框/光环过渡为0秒。自有验收进程已退出，50164预览保持运行。测试使用真实WebView2及受控分析数据、DOM派发事件，不代表模型跟踪质量或操作系统鼠标验收。截图已生成但当前模型不支持图像输入，因此未作人工视觉审阅。
