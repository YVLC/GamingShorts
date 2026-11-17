"""Inspect actual late-caption pixels, not just subtitle sidecars."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,run
import gaming_shorts as gs
import numpy as np

release=gs.ROOT/'Releases/2026-11-14-dialogue-readaloud'
results=[]
for q in read(release/'delivery.json'):
    video=Path(q['output']);timeline=read(video.with_suffix('.captions.json'))['words']
    folder=release/'frame_checks'/q['event'];folder.mkdir(parents=True,exist_ok=True)
    samples=[]
    # Sample one spoken word in every dialogue line, including the final payoff.
    for i,line in enumerate(q['reading_schedule']):
        word=max(line['words'],key=lambda w:w['end']-w['start'])
        t=line['placement']+(word['start']+word['end'])/2-line['cut_start']
        frame=folder/f'line_{i+1:02d}.png'
        run(['ffmpeg','-v','error','-nostdin','-y','-ss',t,'-i',video,'-frames:v','1',frame])
        data=subprocess.run(['ffmpeg','-v','error','-i',str(frame),'-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
        a=np.frombuffer(data,dtype=np.uint8).reshape((1920,1080,3)).astype(int)
        # The caption sits below the sharp gameplay panel. Restrict the pixel
        # check to that region; reject scenery masquerading as yellow text.
        a=a[round(a.shape[0]*.665):round(a.shape[0]*.73)]
        yellow=(a[:,:,0]>180)&(a[:,:,1]>160)&(a[:,:,2]<110)
        count=int(yellow.sum())
        if count<15:raise ValueError(f'Missing visible yellow word: {q["event"]} line {i+1} at {t}')
        samples.append(dict(line=i+1,time=t,yellow_pixels=count,frame=str(frame)))
    results.append(dict(event=q['event'],all_dialogue_lines_have_visible_highlight=True,samples=samples))
save(release/'actual_caption_verification.json',results)
print(json.dumps(results,indent=2))
