"""Native timestamp precision must survive strict null-output decoding."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from source_validation import decode_source

class TimestampValidationTests(unittest.TestCase):
    def test_vfr_native_precision_without_frame_drops(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'variable.mkv'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=96x64:r=60:d=2','-vf','settb=1/1000,setpts=N*16','-enc_time_base','1/1000','-fps_mode','passthrough','-c:v','ffv1',str(source)],check=True,capture_output=True)
            probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
            baseline=subprocess.run(['ffmpeg','-v','error','-i',str(source),'-fps_mode','passthrough','-f','null','-'],capture_output=True,text=True)
            self.assertIn('non monotonically increasing dts',baseline.stderr)
            receipt=decode_source(source,probe)
            self.assertEqual(receipt['frames'],120)

