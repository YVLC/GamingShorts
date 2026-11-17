"""Inspect selected real output frames and report sustained black frames."""
import sys,json,subprocess
from pathlib import Path
from create_visual_stories_v2 import RELEASE,gs,read,run
name=sys.argv[1];receipt=read(RELEASE/(name+'_delivery.json'));video=Path(receipt['output'])
dest=RELEASE/'actual_frames'/name;dest.mkdir(parents=True,exist_ok=True)
duration=gs.duration(video)
words=read(video.with_suffix('.captions.json'))['words']
cta=next(w for w in reversed(words) if w['word'].lower().strip('.,!?')=='subscribe')
cta_time=(cta['start']+cta['end'])/2
for label,t in [('hook',.8),('middle',duration/2),('cta',cta_time)]:
    run(['ffmpeg','-v','error','-y','-ss',t,'-i',video,'-frames:v','1',dest/(label+'.jpg')])
check=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vf','blackdetect=d=0.15:pix_th=0.03','-an','-f','null','-'],capture_output=True,text=True,check=True)
events=[line for line in check.stderr.splitlines() if 'black_start:' in line]
(dest/'black_frame_check.json').write_text(json.dumps({'sustained_black_events':events,'duration':duration,'sha256':receipt['sha256']},indent=2))
print(json.dumps({'event':name,'black_events':events,'frames':str(dest)}))
