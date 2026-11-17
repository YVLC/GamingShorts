"""Synthetic audio test: no network, no Codex, no HeyGen."""
import json,os,shutil,subprocess,tempfile,unittest,wave
from pathlib import Path
import common,gaming_shorts as gs,captions
from voices import request
HERE=Path(__file__).resolve().parents[1]
class DirectTimestampTests(unittest.TestCase):
 def test_real_heygen_timestamps_validate_and_render(self):
  for name in ('storm_v2','shelter_v2'):
   with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);doc=common.read(HERE/'plans'/f'{name}.json')
    common.save(p/'edit_plan.json',doc)
    common.save(p/'manifest.json',{'source':'missing-do-not-read','duration':5430.783})
    v=common.read(HERE/'voice_results'/f'{name}_voice_result.json')
    words=common.read(HERE/'voice_results'/f'{name}_heygen_words.json')
    req=request(doc['clips']);f=p/'VoiceVersions'/common.key(req);(f/'Voices').mkdir(parents=True)
    spans=v['phrases'];cuts=[0]+[(spans[i]['last_word_end']+spans[i+1]['first_word_start'])/2 for i in range(5)]+[v['duration_seconds']]
    files={}
    for i in range(6):
     target=f/'Voices'/f'line_{i+1:02d}.wav'
     with wave.open(str(target),'wb') as w:
      w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*round((cuts[i+1]-cuts[i])*48000))
     files[target.name]=common.digest(target)
    common.save(f/'provenance.json',{'request_key':common.key(req),'files':files})
    common.save(f/'voice_timing.json',{'audio_duration_seconds':v['duration_seconds'],'segment_boundaries':cuts})
    common.save(f/'heygen_word_timestamps.json',words)
    common.save(p/'active_voice.json',{'folder':str(f.relative_to(p))})
    r=captions.align(p)
    self.assertEqual(len(r['lines']),6)
    self.assertEqual(sum(len(x['words']) for x in r['lines']),len(words['words']))
    self.assertTrue('actual source word timestamps' in r['method'])
    self.assertEqual(captions.load(f,doc['clips']),r)
    dest=p/'test.ass';captions.write_ass(dest,r['lines'][0]['words'],360,640,.1)
    s=dest.read_text()
    self.assertIn(r'\1c&H00FFFF&',s)
    self.assertIn(r'\1c&HFFFFFF&',s)
    # Every word gap should retain a subtitle Dialogue event instead of flickering.
    group=captions.groups(r['lines'][0]['words']);first=next(group)
    target=(first[0]['end']+first[1]['start'])/2
    self.assertTrue(any(float(first[0]['end'])<=target<float(first[1]['start']) for _ in [0]))
    if shutil.which('ffmpeg') and name=='storm_v2':
     screenshot=p/'test.jpg'
     cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f','lavfi','-i','color=c=0x142034:s=360x640:r=30:d=3',
          '-vf','ass='+str(dest),'-ss','1.0','-frames:v','1',str(screenshot)]
     subprocess.run(cmd,check=True,timeout=45)
     self.assertGreater(screenshot.stat().st_size,2000)
if __name__=='__main__':unittest.main()
