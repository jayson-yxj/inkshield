"""Create local visual evidence, labelled as candidate IDs not verified people."""
import argparse, json, base64, html
from pathlib import Path
import cv2
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('--cache', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('outputs', type=Path, nargs='+')
a = p.parse_args()
crops = np.load(a.cache / 'crops.npy', mmap_mode='r')
sections = []
for d in a.outputs:
    r = json.loads((d / 'report.json').read_text())
    groups = {}
    for row in r['detections']:
        for f in row['faces']:
            groups.setdefault(f['person'], []).append((row['frame'], f['crop']))
    cards = []
    for pid, items in sorted(groups.items(), key=lambda item: (item[0] is None, item[0] or 0)):
        picks = np.unique(np.linspace(0, len(items)-1, min(8, len(items)), dtype=int))
        figs = []
        for j in picks:
            frame, crop = items[j]
            ok, buf = cv2.imencode('.jpg', crops[crop])
            assert ok
            img = base64.b64encode(buf).decode()
            figs.append(f'<figure><img src="data:image/jpeg;base64,{img}"><figcaption>{frame/r["fps"]:.2f}秒 / 帧{frame}</figcaption></figure>')
        label = f'候选 {pid}' if pid is not None else '待确认样本（可能包含多人）'
        cards.append(f'<article><h3>{label} · {len(items)}次观测</h3><div class="faces">' + ''.join(figs) + '</div></article>')
    sections.append('<section><h2>' + html.escape(r['pack']) + '</h2><p>编号仅在本模型内部有意义，不同模型的相同编号不代表同一个人。</p>' + ''.join(cards) + '</section>')
page = '''<!doctype html><meta charset="utf-8"><title>人脸匹配人工核对</title><style>body{font:16px system-ui;background:#15191b;color:#e3e9eb;padding:24px;margin:auto;max-width:1240px}h1,h2{color:#8ce1bf}article{background:#232b2e;padding:14px;margin:14px 0;border-radius:10px}.faces{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0}img{width:112px;height:112px}figcaption{font-size:12px}p{line-height:1.7}</style><h1>人脸匹配候选核对</h1><p>同一编号的一行中是否出现不同人？同一人是否在多行重复？这些是均匀抽取的示例，未覆盖每一帧；这里没有人工身份标签或准确率结论。请结合完整对照视频，特别核对换镜头、侧脸和模糊片段。</p>''' + ''.join(sections)
a.output.write_text(page, encoding='utf-8')
print(a.output)
