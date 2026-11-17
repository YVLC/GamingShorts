"""Real encoded pixels must follow a moving subject, with no blurred filler."""
import tempfile,unittest,subprocess
from pathlib import Path
import numpy as np
import render_sources

class SubjectTrackingTests(unittest.TestCase):
    def test_edge_trim_removes_native_subtitle_band(self):
        source={'width':1280,'height':720,'duration':1}
        cfg={'width':180,'height':320}
        default,_=render_sources.tracked_filters(source,cfg)
        explicit,_=render_sources.tracked_filters(dict(source,trim_bottom=0),cfg)
        self.assertEqual(default,explicit)
        trimmed,_=render_sources.tracked_filters(dict(source,trim_bottom=.14),cfg)
        # A bright bottom band stands in for native subtitles. The delivered
        # frame must contain only the blue gameplay after trimming.
        raw=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',
            'color=blue:s=1280x720,drawbox=x=0:y=630:w=iw:h=90:color=white:t=fill',
            '-vf',trimmed,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],
            capture_output=True,check=True).stdout
        a=np.frombuffer(raw,np.uint8).reshape(320,180,3)
        self.assertLess(int(a[:,:,0].max()),20)
        self.assertGreater(int(a[:,:,2].min()),220)
        with self.assertRaises(ValueError):
            render_sources.tracked_filters(dict(source,trim_bottom=.5),cfg)

    def test_moving_subject_stays_centered_in_full_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.mkv';target=Path(temp)/'tracked.mkv'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=blue:s=1280x720:r=20:d=1','-f','lavfi','-i','color=white:s=80x80:r=20:d=1','-filter_complex','[0:v][1:v]overlay=x=200+600*t:y=300','-t','1','-c:v','ffv1',str(source)],check=True,capture_output=True)
            graph,meta=render_sources.picture_filters({'width':1280,'height':720,'duration':1,'tracking':[{'at':0,'x':240/1280},{'at':1,'x':840/1280}]},{'width':180,'height':320},'tracked_cover')
            subprocess.run(['ffmpeg','-v','error','-i',str(source),'-vf',graph,'-c:v','ffv1',str(target)],check=True,capture_output=True)
            centers=[]
            for t in (.1,.8):
                raw=subprocess.run(['ffmpeg','-v','error','-ss',str(t),'-i',str(target),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
                a=np.frombuffer(raw,np.uint8).reshape(320,180,3);mask=(a[:,:,0]>220)&(a[:,:,1]>220)&(a[:,:,2]>220)
                self.assertGreater(mask.sum(),300);centers.append(float(np.where(mask)[1].mean()))
                self.assertGreater(a[0,0,2],220);self.assertLess(a[0,0,0],15)
            self.assertTrue(meta['full_frame']);self.assertIsNone(meta['background'])
            for center in centers:self.assertLess(abs(center-90),3)

    def test_invalid_tracking_cannot_reach_renderer(self):
        for path in ([{'at':1,'x':.5}],[{'at':0,'x':float('nan')}],[{'at':0,'x':1.1}],[{'at':0,'x':.5},{'at':0,'x':.6}]):
            with self.assertRaises(ValueError):render_sources.tracking_path(path,2)

if __name__=='__main__':unittest.main()
