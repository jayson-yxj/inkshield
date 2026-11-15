# 隐映 InsightFace 独立 CPU 试验

本试验不修改正式编辑器、分析缓存、打码或导出逻辑；没有生成新的 EXE。

## 模型与实现

- 官方 buffalo_sc：SCRFD-500MF 检测 + MobileFaceNet@WebFace600K 特征提取。
- 官方下载：https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_sc.zip
- 模型包下载大小：14,969,382 bytes。
- det_500m.onnx SHA256：5e4447f50245bbd7966bd6c0fa52938c61474a04ec7def48753668a9d8b4ea3a
- w600k_mbf.onnx SHA256：9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f
- 本机 SDK 不具备完整依赖，安装元数据阶段缺少 Cython；使用隔离适配器复用现有 OpenCV / NumPy / ONNX Runtime CPU。SCRFD 来自保存的官方源码，五点对齐用 NumPy SVD 求相似变换，ArcFace 使用 RGB、112×112、127.5 归一化。
- 每帧检测并提取特征，以余弦相似度匹配首帧模板。试验阈值 0.50，第一/第二候选分差 0.10；同一帧每个人物编号最多分配一次。模糊匹配另建候选编号，不自动合并。尚无运动跟踪、多人模板库、人工纠错或背脸补偿。

## 已完成测试

| 素材 | 全帧数量 | 每帧检测人脸数分布 | 生成的候选编号 |
| --- | ---: | --- | ---: |
| runtime/eb6c3354b20f499b83925d1ae35b0382/input.mp4 | 361 | 0脸40帧，1脸162帧，2脸159帧 | 62 |
| runtime/8e0dd98d134a4179ac7154a88b378e71/input.mp4 | 455 | 1脸452帧，2脸3帧 | 2 |

第二段的编号1出现455帧，编号2仅出现3帧。额外编号可能是真实人脸或误检，未经人工标注不能定性。第一段的62个编号反映这组模型与匹配规则组合有明显碎片化风险，不能把编号数量等同于真实人数。

初次两个进程并发时，中位推理耗时分别为50.39和43.54 ms/帧；这不是独占CPU性能基准。第二段串行复测：中位40.77 ms/帧，P95为46.83 ms/帧，约24.5帧/秒的中位推理速率；结果另见 runtime/insightface-trial-455-serial/report.json。报告计时包含检测、对齐与特征提取，不含解码、编号匹配、原有七类检测或导出。

候选匹配逻辑检查通过：同帧编号不重复；相似候选分差不足时不直接合并。此检查不代表人物识别正确率。

## 如何查看

runtime/insightface-trial-361/review.mp4 与 runtime/insightface-trial-455/review.mp4 是带人物编号的无声审阅视频，未经人工逐帧验收。旁边 report.json 保存逐帧检测框、分数及候选编号，不保存人脸特征向量。人物缩略图仅写入本地试验输出目录。

运行示例：

```powershell
.\.venv\Scripts\python.exe research\insightface_trial.py <视频路径> --output runtime\新目录 --annotate
```

## 结论边界与下一步

- 已验证官方模型可在现有 Windows CPU 环境逐帧运行，并生成候选人物编号。
- 尚未人工标注侧脸角度、真实身份或遮挡区间，不能宣称侧脸识别准确率，也不能认定没有串号。
- 轻量 buffalo_sc 的表现不能代表 buffalo_l/antelopev2 等更大识别模型。官方模型库给出的 buffalo_l CFP-FP 为99.33%，buffalo_s为98.00%，buffalo_sc与buffalo_s识别模型相同；这些是外部基准，不是本应用视频的准确率。
- 当前单模板匹配发现自我强化的编号碎片缺陷：候选分差不足时立即把当前特征登记成新人，重复的同人模板又压低后续匹配分差，可能导致连续新建编号。因此62个编号或更多编号不能证明InsightFace不足，也不能证明需要跟踪器。后续应按人物聚合多模板，暂缓登记模糊候选，并结合人工身份标注比较。
- 不确定身份、完全背脸和漏检帧还没有打码兜底策略，本试验不能用于隐私保护导出。

## 来源与许可

- 官方源码与项目说明：https://github.com/deepinsight/insightface
- 官方模型库：https://github.com/deepinsight/insightface/tree/master/model_zoo
- 代码MIT与模型权重许可需要分开看。官方模型库声明所有预训练模型仅限非商业研究；当前独立验证不等于获得随产品分发或商用许可。
- 下载与源码来源记录保存在 research/insightface-source/provenance.json 及该目录研究记录中。
