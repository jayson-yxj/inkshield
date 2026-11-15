"""Generate the selected splash pixel-eye as scalable artwork and Windows ICO."""
from pathlib import Path
import json,re
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
rows=json.loads(re.search(r'const grid=(\[.*?\]);',(ROOT/'splash-preview.html').read_text(encoding='utf-8')).group(1).replace("'",'"'))
OUT=ROOT/'assets';OUT.mkdir(exist_ok=True)
# Preserve identical 48-pixel silhouette; keep spacing on all sides of the tile.
rects=''.join(f'<rect x="{100+x*25}" y="{125+y*25}" width="19" height="19" rx="3.5"/>' for y,row in enumerate(rows) for x,v in enumerate(row) if v=='1')
(OUT/'inkshield.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect x="16" y="16" width="480" height="480" rx="106" fill="#101114"/><g fill="#b8ed80">'+rects+'</g></svg>',encoding='utf-8')
scale=4
im=Image.new('RGBA',(512*scale,512*scale))
d=ImageDraw.Draw(im);d.rounded_rectangle((16*scale,16*scale,496*scale,496*scale),106*scale,fill='#101114')
for y,row in enumerate(rows):
 for x,v in enumerate(row):
  if v=='1':
   left=(100+x*25)*scale;top=(125+y*25)*scale
   d.rounded_rectangle((left,top,left+19*scale,top+19*scale),3.5*scale,fill='#b8ed80')
im=im.resize((512,512),Image.Resampling.LANCZOS)
im.save(OUT/'inkshield.png');im.save(OUT/'inkshield.ico',sizes=[(n,n) for n in (16,20,24,32,40,48,64,128,256)])
print('Generated SVG, PNG512, ICO16/20/24/32/40/48/64/128/256; 48-pixel splash silhouette')
