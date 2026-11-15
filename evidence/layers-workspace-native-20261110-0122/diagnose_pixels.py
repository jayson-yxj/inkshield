from pathlib import Path
import cv2,av,numpy as np
from PIL import Image
p=Path(__file__).resolve().parent
cap=cv2.VideoCapture(str(p/'source-audio.mp4'));cap.set(cv2.CAP_PROP_POS_FRAMES,19);ok,bgr=cap.read();assert ok
actual=np.asarray(Image.open(p/'jpeg-19.png').convert('RGB'),dtype=float)
ref=np.asarray(Image.open(p/'reference-19.png').convert('RGB'),dtype=float)
ok,j=cv2.imencode('.jpg',bgr,[cv2.IMWRITE_JPEG_QUALITY,88]);decoded=cv2.imdecode(j,1)[:,:,::-1].astype(float)
roi=lambda a:a[65:85,45:65]
for name,img in [('cv',bgr[:,:,::-1]),('jpeg88',decoded),('av',ref)]:print(name,'actual',np.abs(roi(actual)-roi(img)).mean(),'av',np.abs(roi(ref)-roi(img)).mean())
Image.fromarray(decoded.astype('uint8')).save(p/'diagnostic-cv-jpeg19.png')
