#!/usr/bin/env python3
"""Install the actual FREE Garret audio result + word timestamps already returned by HeyGen.

Requires an imported project and matching, unchanged narration. Default previews only.
Use --apply to save the result; then GamingShorts downloads/splits the existing audio.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
SERVER=Path('/mnt/d/GamingShorts/Automation/gamingshorts_v2')
SOURCE=Path('/mnt/d/GamingShorts/Sources/videoplayback (2).mp4')
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--plan',choices=['storm_v2','shelter_v2'],required=True)
 ap.add_argument('--apply',action='store_true')
 args=ap.parse_args()
 if not (SERVER/'start.py').exists():sys.exit('STOP: server not found')
 sys.path.insert(0,str(SERVER))
 import start, gaming_shorts as gs
 from common import config,key,read,save
 from voices import request
 p=start.project_for(SOURCE,'chatgpt_'+args.plan)
 if not (p/'manifest.json').is_file() or not (p/'edit_plan.json').is_file():
  sys.exit('STOP: import '+args.plan+' first')
 doc=gs.validate(p)
 original=read(HERE/'plans'/f'{args.plan}.json')
 if doc!=original:sys.exit('STOP: imported plan has changed. No files modified.')
 result=read(HERE/'voice_results'/f'{args.plan}_voice_result.json')
 words=read(HERE/'voice_results'/f'{args.plan}_heygen_words.json')
 cfg=config();req=request(doc['clips'])
 if result['voice_id']!=cfg['voice_id'] or result['model']!=cfg['voice_model'] or result['model']!='heygen-voice-1-turbo-free':
  sys.exit('STOP: configured voice/model differs from saved FREE recording')
 if words['script']!=req['lines'] or words['voice_id']!=result['voice_id'] or words['model']!=result['model']:
  sys.exit('STOP: words do not match recording and imported plan')
 spans=result['phrases'];duration=float(result['duration_seconds'])
 if len(spans)!=len(doc['clips']):sys.exit('STOP: invalid phrase count')
 cuts=[0.]+[(spans[i]['last_word_end']+spans[i+1]['first_word_start'])/2 for i in range(len(spans)-1)]+[duration]
 for i,(span,clip) in enumerate(zip(spans,doc['clips'])):
  if span['index']!=i+1 or not 0<=span['first_word_start']<span['last_word_end']<=duration+.01:
   sys.exit('STOP: invalid speech phrase')
  if cuts[i+1]-cuts[i]>=clip['duration']-.2:sys.exit(f'STOP: voice line {i+1} too long')
 if len(words['words'])<30:sys.exit('STOP: incomplete word timestamps')
 dest_dir=p/'VoiceVersions'/key(req)
 for name,data in [('voice_result.json',result),('heygen_word_timestamps.json',words)]:
  path=dest_dir/name
  if path.exists() and read(path)!=data:sys.exit('STOP: saved '+name+' conflicts with existing result')
 print('VERIFIED:',args.plan)
 print('Project:',p)
 print('Narration:',round(duration,2),'seconds,',len(spans),'lines,',len(words['words']),'actual word timestamps')
 print('Segments:',[round(cuts[i+1]-cuts[i],2) for i in range(len(spans))])
 if not args.apply:
  print('DRY RUN. Use --apply to safely install, no synthesis or upload.')
  return
 dest_dir.mkdir(parents=True,exist_ok=True)
 for name,data in [('voice_result.json',result),('heygen_word_timestamps.json',words)]:
  path=dest_dir/name
  if not path.exists():save(path,data)
 print('INSTALLED:',dest_dir)
 print('Now run: python3 start.py --project "'+str(p)+'" --stop-after voice')
 print('The server will download and split the ALREADY-generated Garret WAV; no HeyGen/Codex call.')
if __name__=='__main__':
 try:main()
 except Exception as e:sys.exit('STOP: '+str(e))
