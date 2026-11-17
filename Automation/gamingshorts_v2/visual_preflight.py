"""Inspect actual tracked source crops with a representative caption before TTS."""
from pathlib import Path
from common import read,save,key,digest,config,run,HERE
import gaming_shorts as gs
import render_sources,captions,quality_reference

def passes(review):
    return all(review.get(k) is True for k in ('fullscreen','subject_visible','captions_clear','sampled_frames_clear')) and not review.get('issues')

def require_review(project,plan,*,invoke=True):
    if plan.get('editorial',{}).get('policy')!='gaming-stories-v2':return None
    if quality_reference.approved_current(project,plan):return {'status':'exact_user_approved_reference'}
    p=Path(project);cfg=config();m=read(p/'manifest.json')
    identity=key({'plan':plan,'source':m['source_sha256'],'source_stat':Path(m['source']).stat().st_mtime_ns,
        'cfg':cfg,'code':digest(__file__),'renderer':digest(HERE/'render_sources.py'),
        'captions':digest(HERE/'captions.py'),'font':digest(cfg['font'])})
    folder=p/'VisualPreflight'/identity[:20];folder.mkdir(parents=True,exist_ok=True)
    receipt=folder/'review.json'
    if receipt.exists():
        old=read(receipt)
        if old.get('identity')==identity and passes(old.get('review',{})) and old.get('review_key')==key(old['review']) and all(Path(f).is_file() and digest(f)==sha for f,sha in old['image_hashes'].items()):return old
    if not invoke:raise ValueError('Current crop/caption visual review required before narration')
    frames=[];sample_order=[]
    for i,c in enumerate(plan['clips'],1):
        source=render_sources.resolve(m,c,gs.probe);source.update(tracking=c['tracking'],caption_y=c['caption_y'],trim_top=c.get('trim_top',0),trim_bottom=c.get('trim_bottom',0))
        graph,_=render_sources.picture_filters(source,cfg,'tracked_cover')
        # Preview a wide real narration phrase, not only the short hook field.
        tokens=c['narration'].split();fake=[{'word':w,'start':n,'end':n+1} for n,w in enumerate(tokens)]
        phrase=max((' '.join(w['word'] for w in g) for g in captions.groups(fake)),key=len)
        caption=folder/f'caption_{i}.ass'
        preview_words=[{'word':w,'start':n*.2,'end':n*.2+.19} for n,w in enumerate(phrase.split())]
        captions.write_ass(caption,preview_words,cfg['width'],cfg['height'],position_y=c['caption_y'])
        font=folder/'font.ttf'
        if not font.exists():
            import shutil
            shutil.copyfile(cfg['font'],font)
        # Use the production ASS layout and wrapping; drawtext's single-line
        # approximation can falsely report clipping that the export never has.
        overlay=f'setpts=0,ass={caption.name}:fontsdir=.'
        samples=[('start',.15),('middle',c['duration']/2),('end',c['duration']-.15)]
        points=c['tracking']
        for j,point in enumerate(points[1:-1],1):
            if point['x']==points[j-1]['x'] or point['x']==points[j+1]['x']:
                t=point['at']
                if .2<t<c['duration']-.2 and all(abs(t-v)>.2 for _,v in samples):samples.append((f'focus_{j}',t))
            if len(samples)>=6:break
        missing=[]
        for label,t in samples:
            frame=folder/f'shot_{i:02d}_{label}.jpg'
            if not frame.exists():missing.append((label,t,frame))
            frames.append(frame);sample_order.append({'shot':i,'sample':label,'local_time':t})
        if missing:
            # Decode the original once per shot for all requested samples.
            ordered=sorted(missing,key=lambda item:item[1]);fps=float(source['fps'])
            indexes=[round(t*fps) for _,t,_ in ordered]
            select='+'.join(f'eq(n,{n})' for n in indexes)
            pattern=folder/f'extract_{i:02d}_%02d.jpg'
            run(['ffmpeg','-v','error','-nostdin','-y','-threads','2','-ss',source['start'],'-t',source['duration'],'-i',source['path'],
                '-vf',f"setpts=PTS-STARTPTS,{graph},select='{select}',{overlay},setpts=N/({fps}*TB)",
                '-fps_mode','passthrough','-frames:v',len(ordered),pattern],cwd=folder)
            for n,(_,_,frame) in enumerate(ordered,1):
                temp=folder/f'extract_{i:02d}_{n:02d}.jpg'
                if not temp.is_file():raise ValueError('Incomplete sampled crop extraction')
                temp.replace(frame)
    import editorial
    from game_index import cached_ai
    schema=editorial.obj({**{k:{'type':'boolean'} for k in ('fullscreen','subject_visible','captions_clear','sampled_frames_clear')},'issues':{'type':'array','items':editorial.S}})
    prompt=('Review ONLY these actual original-source crop samples: start, middle, end and selected held tracking positions. '
        'Caption text uses the production layout with representative wording and demonstration timing, not final speech timing. '
        'Require fullscreen vertical footage without decorative bars/blur; the important subject or environmental discovery must remain visible. '
        'Reject captions colliding with important native labels/buttons (including the Take button) or obscuring the story evidence. '
        'Reject unintended black/fade samples or a crop that misses the payoff. Native UI text outside the crop is acceptable when unrelated to the story. '
        'Do not claim continuous tracking, sound, final speech synchronization or unseen frames were inspected. '
        'Return strict JSON only, no tools. Image order: '+str(sample_order)+' Plan: '+str(plan))
    review=cached_ai(folder,prompt,schema,frames,'crop_caption_review')
    result={'identity':identity,'review':review,'review_key':key(review),'image_hashes':{str(f):digest(f) for f in frames},
        'scope':'Sampled source crop and representative caption clearance only; final media and listening remain separate.'}
    save(receipt,result)
    if not passes(review):raise ValueError('Crop/caption preflight rejected before narration: '+str(review['issues']))
    return result
