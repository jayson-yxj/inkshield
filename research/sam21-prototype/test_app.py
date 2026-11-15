import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from fastapi.testclient import TestClient
import app

class Contract(unittest.TestCase):
 def test_masks_exports_validation_and_revision(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'in.mp4';w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,48))
   for i in range(5):w.write(np.full((48,64,3),100+i*5,np.uint8))
   w.release()
   class Fake:
    def segment(self,folder,prompts,count,**kwargs):
     m=np.zeros((48,64),np.uint8);m[10:30,20:40]=1
     return {i:m.copy() for i in range(count)},{'test':True}
   with patch.object(app,'DATA',Path(tmp)),patch.object(app,'ENGINE',Fake()),TestClient(app.app) as c:
    with path.open('rb') as f:r=c.post('/api/import',files={'video':('v.mp4',f,'video/mp4')})
    self.assertEqual(r.status_code,200,r.text);s=r.json();sid=s['id']
    self.assertEqual(c.post('/api/export/'+sid,json={}).status_code,409)
    self.assertEqual(c.post('/api/segment/'+sid,json={'prompts':{'0':[{'x':float(100),'y':20,'label':1}]}}).status_code,422)
    r=c.post('/api/segment/'+sid,json={'prompts':{'0':[{'x':25,'y':20,'label':1}]}});self.assertEqual(r.status_code,200)
    import time
    def wait(j):
     for _ in range(100):
      state=c.get('/api/job/'+j).json()
      if state['state'] in ('done','error'):self.assertEqual(state['state'],'done',state);return state
      time.sleep(.02)
     self.fail('timeout')
    wait(r.json()['job_id'])
    self.assertEqual(c.post('/api/segment/'+sid,json={'prompts':{'0':[{'x':25,'y':20,'label':1}],'2':[{'x':1,'y':1,'label':0}]}}).status_code,422)
    saved=app.SESSIONS[sid]['masks'][0];app.SESSIONS[sid]['masks'][0]=np.zeros_like(saved)
    self.assertEqual(c.post('/api/export/'+sid,json={}).status_code,409)
    app.SESSIONS[sid]['masks'][0]=saved
    r=c.get(f'/api/mask/{sid}/0.png');mask=cv2.imdecode(np.frombuffer(r.content,np.uint8),-1);self.assertEqual(mask.shape,(48,64,4))
    self.assertEqual(c.get(f'/api/preview/{sid}/0.jpg?style=bad').status_code,422)
    image=cv2.imread(str(app.SESSIONS[sid]['folder']/'frames/00000.jpg'))
    result=app.render(image,app.SESSIONS[sid]['masks'][0],'black',68,0);self.assertFalse(result[10:30,20:40].any());self.assertTrue(np.array_equal(result[:10],image[:10]))
    r=c.post('/api/export/'+sid,json={'style':'black','padding':0});done=wait(r.json()['job_id']);self.assertEqual(done['frames'],5);self.assertEqual(c.get(done['download']).status_code,200)
    self.assertEqual(c.get(f'/api/download/{sid}/bad.mp4').status_code,404)
if __name__=='__main__':unittest.main()
