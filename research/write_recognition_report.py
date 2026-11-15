"""Write a results report from completed measured artifacts."""
from pathlib import Path
import json
root=Path('runtime');out=root/'recognition-three-model-review';summary=json.loads((out/'summary.json').read_text());bench=json.loads((root/'recognition-benchmark.json').read_text());rows=summary['models'];timings=bench['results']
assert len(rows)==len(timings)==3
assert [r['model'] for r in rows]==['MobileFaceNet','ArcFace-ResNet50','AdaFace-IR50']
assert ['w600k_mbf.onnx','w600k_r50.onnx','adaface_ir50_ms1mv2.onnx']==[Path(t['model']).name for t in timings]
lines=['# 三种人脸匹配网络：同一原片隔离对照','', '输入为桌面5.mp4，1280×720、25fps、6454帧、258.16秒。统一SCRFD-500MF检测和五点对齐，共11383张112×112人脸裁剪，逐帧检测框与前一轮完全相同。缓存重跑的轻量基线逐帧复现上一轮所有人物编号。','', '## 实测结果','', '| 网络 | 候选编号 | 已分配 | 待确认 | 待确认占比 | 相邻高重叠非空换号 | 独立识别耗时中位数/P95 |','|---|---:|---:|---:|---:|---:|---:|']
for r,t in zip(rows,timings):
 lines.append(f"| {r['model']} | {r['candidate_ids']} | {r['assigned']} | {r['pending']} | {r['pending_fraction']*100:.2f}% | {r['adjacent_high_overlap_nonnull_changes']} | {t['median_ms']:.1f} / {t['p95_ms']:.1f} ms |")
lines+=['','识别速度采用共同的200张均匀抽样裁剪，4线程CPU、单张推理、先预热5张，三个模型依次单独运行。仅包括人脸裁剪预处理和特征提取，不包括检测、解码、身份关联和编码；单次测量会受系统负载和温度影响，不代表完整软件帧率。各网络另有全11383张推理耗时记录；轻量全量运行有短时导出校验重叠，速度比较优先用独立200张测试。','', '## 如何审阅','', 'comparison.mp4并排显示MobileFaceNet、ArcFace ResNet50、AdaFace IR50，绿色数字为各自候选编号，黄色问号表示待确认。全片重新解码核验6454帧。不同网络相同编号不对应同一个人。','', '人物核对.html为每个候选编号均匀抽取最多8张脸，并补充待确认样本，带时间和帧号。请检查同一行是否出现不同人、不同编号行是否重复同一个人，再结合视频看换镜头、侧脸、模糊片段。均匀抽样不能保证覆盖短暂串人。','', '## 能确认和仍未知的部分','', '本次确认三个识别网络均能在本地CPU上处理全片检测到的人脸，并取得可复核的关联诊断。没有人工身份标签，不能把编号数、低待确认率或零相邻换号解释为真实人数、识别准确率或模型优胜。相邻高重叠框仅是局部几何连续性参照，无法验证跨镜头身份。','', '所有网络使用同一冻结的建档规则：匹配0.50/分差0.10、登记相似度低于0.40、连续5帧确认、暂存一致0.65/分差0.10、最多6模板；更新分数0.60/分差0.15/锚点0.45/新颖性低于0.90。登记和更新要求检测分数≥0.70、脸短边≥40像素。所有相似度门槛都依赖模型特征分布，尚未按人工标签校准。阈值扫描仅改变正式匹配阈值，不是完整参数优化。','', '同帧不重叠人脸和相邻IoU≥0.90人脸的特征相似度诊断单独存档：前者仍可能是镜像或屏幕中的同一人，后者可能受切镜头影响且大量重复容易样本，因此不据此报告准确率。','', '下一步应人工确认有代表性的跨镜头同人/不同人、正脸/侧脸/模糊脸，再分别校准阈值并评估串人、拆号和待确认比例。当前结果足以筛查运行成本和关联行为，但尚不足以选定正式替换模型。','', '## 实现、来源和保留范围','', 'ArcFace使用官方InsightFace v0.7 buffalo_l压缩包中的w600k_r50.onnx。AdaFace使用作者CVLFace IR50 MS1MV2 safetensors，按作者架构导出ONNX；PyTorch与ORT特征最大误差3.09e-7。作者新版权重与取得的旧格式检查点副本比较，467个状态张量中466完全相同，唯一不同的首层卷积恰好交换输入颜色通道，故此次使用RGB输入；旧副本仅用于数值等价核验，本次实际推理使用作者新版权重。三者输入均为RGB、(x−127.5)/127.5，输出归一化后比较余弦相似度。','', '原片SHA256：5d54f47d20f78bd60af6a2d30e330011c09d472b1109afaf249c1952a9efbb9c。模型哈希、来源及预处理核验另见研究目录的provenance和validation记录。','', '素材未上传外部服务。为重复分析，本次独立runtime目录保留对齐人脸裁剪和embeddings.npy特征，不沿用此前仅内存特征的说明。正式UI、EXE和生产依赖未修改，研究素材和权重不加入发布包。InsightFace预训练权重限非商业研究；AdaFace代码MIT，权重商业再分发及训练数据授权未获独立确认。']
lines+=['','## 建议重点复核','', 'AdaFace在第2312帧（92.48秒，约1分32秒）出现一次相邻高重叠框的非空编号变化：14→13，框IoU约0.872。这是几何诊断命中，尚未人工确认是否为真实身份切换。轻量网络和ArcFace在同一诊断规则下均为0次；0次也不代表没有跨镜头串人。','']
lines+=['','## 正式匹配阈值敏感性','', '| 网络 | 匹配阈值 | 候选编号 | 待确认 |','|---|---:|---:|---:|']
for folder in ['recognition-mobileface','recognition-arcface-r50','recognition-adaface-ir50']:
 sweep=json.loads((root/folder/'threshold-sweep.json').read_text())
 pack=json.loads((root/folder/'report.json').read_text())['pack']
 for item in sweep['results']:
  lines.append(f"| {pack} | {item['threshold']:.2f} | {item['candidate_ids']} | {item['pending']} |")
lines+=['','该表仅说明固定建档策略下对单一门槛的敏感性，没有人工身份真值，不能用最少待确认来选择最佳阈值。']
(out/'测试报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print(out/'测试报告.md')
