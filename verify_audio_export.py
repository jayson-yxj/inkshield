"""Real mux regression: segment audio timing/content, silent mode, failure closure."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from fastapi.testclient import TestClient
import server
from audio_export import has_audio
import subprocess
import imageio_ffmpeg

def run_ffmpeg(arguments):
    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-nostdin',*arguments],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    return result.returncode,result.stderr.decode(errors='replace')


class AudioExportTests(unittest.TestCase):
    def test_audio_segment_and_muted_and_missing_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            silent = root/'silent.mp4'
            writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'mp4v'), 10, (64,48))
            self.assertTrue(writer.isOpened())
            for n in range(30): writer.write(np.full((48,64,3), n*5, np.uint8))
            writer.release()
            original = root/'with-audio.mp4'
            # Chirp changes pitch continuously, so an incorrect zero-based trim is detectable.
            code, log = run_ffmpeg(['-i',str(silent),'-f','lavfi','-i','aevalsrc=0.25*sin(2*PI*(220*t+110*t*t)):s=48000:d=3',
                '-map','0:v','-map','1:a','-c:v','copy','-c:a','aac',str(original)])
            self.assertEqual(code,0,log)
            self.assertTrue(has_audio(original));self.assertFalse(has_audio(silent))
            for muted, source, expected in [(True,original,False),(False,original,True),(False,silent,False)]:
                job='audio-'+str(muted)+source.stem
                output=root/(job+'.mp4')
                analysis=server.Analysis(source,tuple(() for _ in range(10)),64,48,10,start_frame=10,face_ids=tuple(() for _ in range(10)))
                server.new_job(job,'export',muted=muted)
                server.export_video(job,analysis,output,('face',),68,'black',muted)
                self.assertEqual(server.require_job(job)['state'],'done')
                self.assertEqual(server.require_job(job)['audio_present'],expected)
                self.assertEqual(has_audio(output),expected)
                cap=cv2.VideoCapture(str(output));count=0
                while cap.read()[0]: count+=1
                cap.release();self.assertEqual(count,10)
                if expected:
                    pcm=root/'audio.f32'
                    code,log=run_ffmpeg(['-i',str(output),'-map','0:a','-ac','1','-ar','48000','-f','f32le',str(pcm)])
                    self.assertEqual(code,0,log)
                    samples=np.fromfile(pcm,np.float32)
                    self.assertLess(abs(len(samples)/48000-1),.04)
                    self.assertGreater(float(np.sqrt(np.mean(samples**2))),.1)
                    # At segment midpoint original t=1.5 gives 550 Hz, not zero-based 330 Hz.
                    block=samples[20000:28000];freq=np.fft.rfftfreq(len(block),1/48000)[np.argmax(abs(np.fft.rfft(block)))]
                    self.assertGreater(freq,480);self.assertLess(freq,620)
            job='audio-fail';output=root/'failure.mp4';server.new_job(job,'export')
            analysis=server.Analysis(original,tuple(() for _ in range(10)),64,48,10,start_frame=10,face_ids=tuple(() for _ in range(10)))
            with patch('audio_export.mux_segment_audio',side_effect=RuntimeError('mux failed')):
                with self.assertRaisesRegex(RuntimeError,'mux failed'):
                    server.export_video(job,analysis,output,('face',),68,'black',False)
            self.assertFalse(output.exists());self.assertFalse((root/'video-only.mp4').exists())
            # API default and explicit mute values are frozen into job/worker arguments.
            with patch.object(server,'require_analysis',return_value=analysis),patch.object(server,'RUNTIME',root),patch.object(server,'start_worker') as worker:
                client=TestClient(server.app)
                try:
                    for data, expected in [({},True),({'muted':'false'},False)]:
                        response=client.post('/api/export/test',data=data);self.assertEqual(response.status_code,200,response.text)
                        self.assertEqual(worker.call_args.args[7],expected)
                        self.assertEqual(server.require_job(response.json()['job_id'])['muted'],expected)
                        server.ACTIVE_JOBS.release()
                finally: client.close()


if __name__=='__main__': unittest.main(verbosity=2)
