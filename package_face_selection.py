"""Package the tested local face-selection trial, excluding user media and caches."""
from pathlib import Path
import hashlib,json,zipfile,shutil
root=Path(__file__).resolve().parent
build=root/'dist/timeline-editing-trial'
exe=build/'Inkshield.exe'
assert exe.is_file()
sha=hashlib.sha256(exe.read_bytes()).hexdigest()
readme='''隐映 · 时间线编辑本地试用版

解压后双击 Inkshield.exe。Windows x64；使用 CPU，本地处理，无需下载模型。
如系统缺少 WebView2，程序会尝试使用默认浏览器，保留本地服务窗口。

导入视频 → 选择片段 → 一键分析。
处理目标只保留“人脸”和“车牌”；人脸使用 SCRFD + MobileFaceNet。
“全部人脸”遮住所有检测到的人脸，包括待确认人脸。
“指定人物”点击人物缩略图选择要遮住的编号；默认同时遮住待确认人脸。
取消“待确认人脸也打码”后，无法确认身份的人脸会保持可见，请逐段核对。
编号只属于当前分析，跨片段不共享；重新分析清空选择。编号可能把同一人拆成多个，也可能混淆，请检查缩略图与预览。
初始确认前的画面仍为待确认，不会事后自动改写身份。
人脸遮罩可选内接椭圆（贴合检测框四边）或外接椭圆（经过检测框四角），默认外接；车牌保持矩形。形状随片段保存。
可以取消全部处理目标，预览和导出均不添加遮罩；这仍是视频导出，并非原文件直接复制。
可选马赛克、高斯模糊、方框模糊、横向模糊、纵向模糊或黑色色块；各片段独立保存设置，导出固定点击时设置。
扬声器按钮同时控制预览和导出是否静音，沿用原版本默认静音；需要原声时请先取消静音。
已分析片段拖动定位优先使用本机解码画面与缓存遮罩，等待新帧时保留上一张画面；解码速度仍取决于视频编码和电脑性能。
每个切分处显示分割点：点击选中，拖动调整两侧区间，点击删除分割点可合并相邻片段。合并继承左侧遮罩设置。
边界移动或合并后，受影响片段须重新分析；其余片段缓存保留。撤销可恢复此前区间、缓存和设置。
启动动画、内置教程、时间轴缩放、分割与撤销仍保留。

数据：原视频副本、检测缓存、未打码人物缩略图与导出保存在本机 %LOCALAPPDATA%\\Inkshield\\runtime，关闭界面不会自动清空；请按自己的隐私要求管理该目录。
分析与导出可占用CPU；任务运行中关闭窗口会提示并停止任务。

许可：这是授权的个人本地非商业研究试用构建。InsightFace 预训练权重限非商业研究，本构建未取得公开分发或商业使用许可。可运行不表示可公开再分发。详见模型来源与打包说明。
本机验证不能代替另一台全新Windows机器兼容性验收。检测/身份分组可能漏检或混淆，导出前检查需要保护的画面。
'''
(build/'使用说明.txt').write_text(readme,encoding='utf-8')
(build/'SHA256.txt').write_text(sha.upper()+'  Inkshield.exe\n',encoding='utf-8')
for name in ['PACKAGING_REPORT.md','PACKAGING_DEPENDENCIES.json','requirements-packaging.lock.txt','AUDIO_DEPENDENCIES.md']:
    shutil.copy2(root/name,build/name)
# Correct changed output path in the external copy without altering frozen sources.
p=build/'PACKAGING_REPORT.md'
p.write_text(p.read_text(encoding='utf-8').replace('dist/人物打码试用版/Inkshield.exe','dist/timeline-editing-trial/Inkshield.exe'),encoding='utf-8')
for name in ['FACE_SOURCE.md','INSIGHTFACE_LICENSE.txt','HYPERLPR_SOURCE.md']:
    shutil.copy2(root/'models'/name,build/name)
licenses=root/'dist/隐映-Windows-x64-内置教程版/第三方许可证'
if licenses.is_dir():shutil.copytree(licenses,build/'第三方许可证',dirs_exist_ok=True)
archive=root/'dist/隐映-Windows-x64-时间线编辑版.zip'
files=sorted(p for p in build.rglob('*') if p.is_file())
assert not any(p.suffix.lower() in ['.mp4','.npy','.onnx'] for p in files)
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in files:z.write(p,p.relative_to(build).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert hashlib.sha256(z.read('Inkshield.exe')).hexdigest()==sha
record={'exe_sha256':sha,'exe_bytes':exe.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,'files':[str(p.relative_to(build)) for p in files]}
(root/'runtime/timeline-editing-package.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
print(archive)
