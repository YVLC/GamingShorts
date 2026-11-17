"""Verify delivered bytes and visible yellow captions in every spoken shot/CTA."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,run,digest
import gaming_shorts as gs
import numpy as np

release=gs.ROOT/'Releases/2026-11-15-story-reuse';results=[]
for receipt in sorted(release.glob('*_delivery.json')):
    event=receipt.name.removesuffix('_delivery.json');delivery=read(receipt);q=delivery['qc'];video=Path(delivery['output'])
    if digest(video)!=delivery['sha256'] or q['status']!='technical_pass':raise ValueError('Delivered bytes or QC changed')
    plan=read(release/(event+'_plan.json'))['plan'];words=read(video.with_suffix('.captions.json'))['words']
    samples=[];offset=0
    for i,c in enumerate(plan['clips']):
        selected=[w for w in words if offset<=w['start']<offset+c['duration']]
        if not selected:raise ValueError('Shot has no speech captions')
        word=max(selected,key=lambda w:w['end']-w['start']);samples.append((f'shot_{i+1:02d}',word));offset+=c['duration']
    cta=[w for w in words if w['word'].lower().strip('.,!?')=='subscribe']
    if len(cta)!=1 or cta[0]['start']<offset-plan['clips'][-1]['duration']:raise ValueError('Closing CTA missing or misplaced')
    samples.append(('closing_cta',cta[0]))
    size=gs.probe(video);vs=next(s for s in size['streams'] if s['codec_type']=='video');width,height=int(vs['width']),int(vs['height'])
    folder=release/'final_frames'/event;folder.mkdir(parents=True,exist_ok=True);checks=[]
    for label,word in samples:
        t=(word['start']+word['end'])/2;frame=folder/(label+'.png')
        run(['ffmpeg','-v','error','-nostdin','-y','-ss',t,'-i',video,'-frames:v','1',frame])
        raw=subprocess.run(['ffmpeg','-v','error','-i',str(frame),'-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
        pixels=np.frombuffer(raw,np.uint8).reshape(height,width,3).astype(int)[round(height*.655):round(height*.74)]
        yellow=(pixels[:,:,0]>180)&(pixels[:,:,1]>160)&(pixels[:,:,2]<110)
        count=int(yellow.sum())
        if count<15:raise ValueError('Missing yellow caption in '+event+' '+label)
        checks.append({'label':label,'time':t,'word':word['word'],'yellow_pixels':count,'frame':str(frame)})
    project=Path(read(release/(event+'_plan.json'))['project'])
    if not gs.completed(project):raise ValueError('Current project identity no longer matches delivered output')
    results.append({'event':event,'output':str(video),'sha256':delivery['sha256'],'status':'passed','checks':checks,'music':q['music']['title'],'instrumental':q['music'].get('instrumental'),'trend_verified':q['music'].get('trend_verified',False),'duration':q['actual_duration'],'warnings':q['warnings'],'listening_review':'not_performed'})
save(release/'delivery-verification.json',results)
print(json.dumps(results,indent=2))
