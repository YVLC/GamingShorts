"""Check actual exported frames, not proxy or caption-preview images."""
import sys,json,subprocess,re
from pathlib import Path
from create_batch_three import v
from common import read,save,run,digest
names=[sys.argv[1]] if len(sys.argv)>1 else list(v.CHOICES)
for name in names:
    receipt=read(v.RELEASE/(name+'_delivery.json'));video=Path(receipt['output']);duration=v.gs.duration(video)
    words=read(video.with_suffix('.captions.json'))['words']
    subscribe=next(w for w in reversed(words) if w['word'].lower().strip('.,!?')=='subscribe')
    folder=v.RELEASE/'actual_frames'/name;folder.mkdir(parents=True,exist_ok=True)
    times={'hook':.9,'middle':duration/2,'cta':(subscribe['start']+subscribe['end'])/2}
    if name=='batch3_hand_grip':times['condition_result']=duration-1.5
    if name=='batch3_chamber_light':times['lighting_action']=12.5
    for label,t in times.items():run(['ffmpeg','-v','error','-y','-ss',t,'-i',video,'-frames:v','1',folder/(label+'.jpg')])
    black=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vf','blackdetect=d=0.15:pix_th=0.03','-an','-f','null','-'],capture_output=True,text=True,check=True)
    events=[line for line in black.stderr.splitlines() if 'black_start:' in line]
    known_path=v.RELEASE/'source_transition_evidence'/(name+'.json');known=read(known_path) if known_path.exists() else {}
    if known and (known['output_sha256']!=receipt['sha256'] or digest(known['source_log'])!=known['source_log_sha256']):raise ValueError('Source transition evidence changed')
    unexplained=[]
    for event in events:
        values={k:float(value) for k,value in re.findall(r'(black_start|black_end|black_duration):([0-9.]+)',event)}
        if not any(abs(values['black_start']-a)<.03 and abs(values['black_end']-b)<.03 for a,b in known.get('output_intervals',[])):unexplained.append(event)
    save(folder/'verification.json',{'output_sha256':receipt['sha256'],'duration':duration,'sustained_black_events':events,'sample_times':times,
        'unexplained_black_events':unexplained,'source_transition_evidence':known,
        'listening_review':'not_performed','technical_status':receipt['qc']['status']})
    if unexplained:raise ValueError('Sustained black frames need inspection: '+str(unexplained))
    print(name+': final frame extraction and black-frame check passed',flush=True)
