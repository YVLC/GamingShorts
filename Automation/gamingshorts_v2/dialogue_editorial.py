"""Dialogue-aware editorial policy; legacy narrated projects keep their pipeline."""
import json,math,re,difflib,shutil,subprocess
from pathlib import Path
from common import read,save,key,digest,config,now,run,verified_source_receipts
import gaming_shorts as gs
from game_store import GameStore,overlaps
from game_index import cached_ai,checked_recording,verify_integrity
import editorial,creative_history,shared_index

VERSION='dialogue-editorial-v1'
MODES=('narrated','hybrid','gameplay-first')
FLAGS=('supported','curiosity_or_interest','natural_pacing','emotional_or_comedic_value','event_clear',
       'nonredundant_narration','narration_adds_value','chronological','no_unnecessary_cuts','satisfying_ending',
       'dialogue_faithful','no_invented_character_audio')
REVIEW=editorial.obj(dict({k:{'type':'boolean'} for k in FLAGS},score={'type':'number','minimum':0,'maximum':1},
    issues={'type':'array','items':editorial.S},reason=editorial.S))
LINE=editorial.obj({'start':editorial.N,'end':editorial.N,'text':editorial.S,'confidence':{'type':'number','minimum':0,'maximum':1},'evidence':editorial.S})
EVIDENCE=editorial.obj({'events':{'type':'array','items':editorial.obj({'event_id':editorial.S,'scene_id':editorial.S,
    'visible_event':editorial.S,'outcome':editorial.S,'dialogue':{'type':'array','items':LINE},
    'dialogue_coverage':editorial.S,'uncertainties':{'type':'array','items':editorial.S}})}})
CHOICE=editorial.obj({'event_id':editorial.S,'scene_id':editorial.S,'suitable':{'type':'boolean'},'premise':editorial.S,
    'hook':editorial.S,'mode':{'type':'string','enum':list(MODES)},'start':editorial.N,'duration':editorial.N,
    'commentary':editorial.S,'narration_rationale':editorial.S,'added_value':editorial.S,'ending':editorial.S,
    'duration_reason':editorial.S,'reason':editorial.S,'mood':{'type':'string','enum':['suspense','epic','funny','relaxed','action']}})
COMPARISON=editorial.obj({'candidates':{'type':'array','minItems':3,'maxItems':3,'items':CHOICE},'comparison':editorial.S})

def is_plan(doc):return doc.get('editorial',{}).get('policy')==VERSION
def normalized(text):return ' '.join(re.findall(r"[a-z0-9]+",text.lower()))

def redundancy(text,dialogue):
    """Literal blockers only. Semantic and obvious-action redundancy need review."""
    text=normalized(text)
    if not text:return []
    problems=[]
    if re.search(r'\b(now she says|then she says|then asks|then the apology|here we see)\b',text):
        problems.append('Recap/announced-reaction phrasing requires added-value revision')
    for row in dialogue:
        other=normalized(row['text'])
        if len(other.split())>=3 and (text==other or difflib.SequenceMatcher(None,text,other).ratio()>.86):
            problems.append('Narration repeats visible dialogue: '+row['text'])
        a=set(zip(text.split(),text.split()[1:],text.split()[2:]));b=set(zip(other.split(),other.split()[1:],other.split()[2:]))
        if a and len(a & b)/len(a)>.6:problems.append('Narration substantially repeats dialogue phrases')
    return problems

def validate(doc,meta):
    ed=doc.get('editorial',{});mode=ed.get('mode');clips=doc.get('clips')
    if mode not in MODES:raise ValueError('Unknown dialogue editorial mode')
    if not isinstance(clips,list) or not 1<=len(clips)<=6:raise ValueError('Use 1–6 meaningful shots, including one continuous scene')
    end=-1;total=0;spoken=[]
    for c in clips:
        a=float(c['start']);d=float(c['duration'])
        if not all(math.isfinite(x) for x in (a,d)) or a<0 or not 2<=d<=45 or a+d>float(meta['duration'])+.02:raise ValueError('Invalid source timing')
        if a<end-.001:raise ValueError('Chronology or source uniqueness violated')
        if end>=0 and not c.get('cut_reason','').strip():raise ValueError('Every cut needs a genuine downtime/removal reason')
        hold=float(c.get('end_reading_hold',0))
        if not math.isfinite(hold) or not 0<=hold<=2 or (hold and (mode not in ('gameplay-first','hybrid') or c is not clips[-1])):raise ValueError('Reading hold must be an explicit final dialogue reading freeze, at most two seconds')
        end=a+d;total+=d+hold
        if not isinstance(c.get('narration'),str) or len(c['narration'])>350:raise ValueError('Invalid commentary')
        if not isinstance(c.get('caption'),str):raise ValueError('Invalid caption')
        if c['narration'].strip():spoken.append(c)
        if redundancy(c['narration'],ed.get('dialogue',[])):raise ValueError('; '.join(redundancy(c['narration'],ed.get('dialogue',[]))))
    if not 8<=total<=45:raise ValueError('Complete moments must fit 8–45 seconds; 15–25 preferred')
    if not ed.get('duration_reason','').strip():raise ValueError('Explain why this duration completes the story without padding')
    if mode=='gameplay-first' and spoken:raise ValueError('Gameplay-first must not synthesize narration or character speech')
    if mode=='narrated' and len(spoken)!=len(clips):raise ValueError('Narrated mode requires commentary for every shot')
    if mode=='hybrid' and (not spoken or sum(len(c['narration'].split())/2 for c in spoken)>total*.4):raise ValueError('Hybrid commentary must be a brief addition, not a recap track')
    if spoken and not ed.get('added_value','').strip():raise ValueError('Commentary needs a concrete added-value rationale')
    if not ed.get('cta',False) and any('subscribe' in normalized(c['narration']) for c in clips):raise ValueError('Unrequested generic subscription ending')
    for line in ed.get('dialogue',[]):
        if not all(math.isfinite(float(line[k])) for k in ('start','end','confidence')) or not 0<=line['confidence']<=1 or not 0<=line['start']<line['end']<=float(meta['duration']) or not line['text'].strip():raise ValueError('Invalid source dialogue evidence')
    return doc

def review_passes(review,mode='narrated'):
    required=tuple(k for k in FLAGS if not (mode=='gameplay-first' and k=='narration_adds_value'))
    return all(review.get(k) is True for k in required) and not review.get('issues') and review.get('score',0)>=.85

def guard(project,doc,require_active=True):
    p=Path(project);m=read(p/'manifest.json');validate(doc,m);store=GameStore();r=store.recording(m['full_game']['recording']);checked_recording(r)
    if require_active and store.recording()['id']!=r['id']:raise ValueError('Different active source')
    if m.get('source_bundle') or m['source']!=r['source'] or m['source_sha256']!=r['sha256']:raise ValueError('Finals must use the authoritative original')
    scenes={s['id']:s for s in store.scenes(r['id'])}
    from dialogue_mission import eligible
    for c in doc['clips']:
        s=scenes.get(c['scene_id'])
        if not s or c['start']<s['start'] or c['start']+c['duration']>s['end'] or not eligible(s,store,project=p):raise ValueError('Unapproved, reused or out-of-evidence source footage')
    proof=read(p/'dialogue_editorial_review.json')
    if proof['plan_key']!=key(doc) or not review_passes(proof['review'],doc['editorial']['mode']):raise ValueError('Current independent editorial-quality review required')
    if any(not Path(name).is_file() or digest(name)!=sha for name,sha in proof['evidence_images'].items()):raise ValueError('Dialogue evidence changed')
    creative_history.require_review(p,doc)
    return r

def fingerprint(p,doc,music,voice):
    files={str(x):digest(x) for x in Path(voice).rglob('*') if x.is_file() and x.name in ('provenance.json','word_alignment.json','heygen_full.wav')} if voice else {}
    if voice:
        files.update({str(x):digest(x) for x in (Path(voice)/'Voices').glob('*.wav')})
    return key({'policy':VERSION,'code':digest(__file__),'plan':doc,'manifest':read(Path(p)/'manifest.json'),'config':config(),'music':music,'voice_files':files,
        'code_hashes':{name:digest(Path(__file__).with_name(name)) for name in ('gaming_shorts.py','render_sources.py','music_mix.py','music_library.py','music_segments.py','music_composer.py','quality_checks.py','audio_pipeline.py','audio_checks.py','captions.py')},
        'font':digest(config()['font']),'editorial_review':read(Path(p)/'dialogue_editorial_review.json')})

def completed(project):
    p=Path(project)
    try:
        q=read(p/'qc_report.json');doc=read(p/'edit_plan.json');validate(doc,read(p/'manifest.json'))
        v=read(p/'dialogue_render_inputs.json');voice=Path(v['voice_folder']) if v.get('voice_folder') else None
        if q['status']!='technical_pass' or not Path(q['output']).is_file() or digest(q['output'])!=q['output_sha256']:return False
        if q['input_key']!=fingerprint(p,doc,read(p/'music_selection.json'),voice):return False
        if doc['editorial']['mode']!='gameplay-first' and not voice:return False
        return True
    except (OSError,KeyError,ValueError,TypeError):return False

def presentation_windows(lines,start,seconds):
    ordered=sorted(lines,key=lambda line:line['start']);result=[]
    for i,line in enumerate(ordered):
        a=max(0,line['start']-start);b=min(seconds,line['end']-start)
        next_start=ordered[i+1]['start']-start if i+1<len(ordered) else seconds
        b=min(seconds,next_start,max(b,a+min(5,max(1.5,len(line['text'].split())/3))))
        if a<b and line['confidence']>=.9:result.append(dict(line,start=a,end=b))
    return result

def subtitle_ass(path,lines,start,seconds,width,height):
    """Faithful visible-line timing, explicitly not invented speech/word timing."""
    import captions
    header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,DejaVu Sans,{round(width*.048)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,250,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    rows=[]
    for line in presentation_windows(lines,start,seconds):
        a,b=line['start'],line['end']
        if a<b and line['confidence']>=.9:
            rows.append(f"Dialogue: 0,{captions.stamp(a,True)},{captions.stamp(b,True)},Default,,0,0,0,,{captions.escape(line['text'])}")
    path.write_text(header+'\n'.join(rows)+'\n',encoding='utf-8')

def render(project,voice_folder=None):
    import render_sources,quality_checks,music_library,music_mix,captions,audio_pipeline
    from audio_checks import indicators
    p=Path(project);doc=read(p/'edit_plan.json');r=guard(p,doc);m=read(p/'manifest.json');cfg=dict(config())
    spoken=[(i,c) for i,c in enumerate(doc['clips']) if c['narration'].strip()]
    if spoken and not voice_folder:raise ValueError('Declared commentary cannot render without verified speech')
    if not spoken and voice_folder:raise ValueError('Unvoiced editorial mode cannot attach synthetic speech')
    align=captions._from_saved_heygen_words(voice_folder,[c for _,c in spoken]) if spoken else None
    if spoken and not align:raise ValueError('Real speech word timestamps required')
    music=music_library.select(p)
    if not music.get('path'):raise ValueError('No cleared music available; no unlicensed replacement')
    fp=fingerprint(p,doc,music,voice_folder)
    if completed(p):return Path(read(p/'qc_report.json')['output'])
    out=p/'Renders'/fp[:16];out.mkdir(parents=True,exist_ok=True);shutil.copyfile(cfg['font'],out/'font.ttf')
    if spoken:
        provenance=read(Path(voice_folder)/'provenance.json')
        for name,sha in provenance['files'].items():
            if digest(Path(voice_folder)/'Voices'/name)!=sha:raise ValueError('Speech bytes changed')
    verify_integrity(r)
    with verified_source_receipts({r['source']:{'sha256':r['sha256'],'fingerprint':json.loads(r['fingerprint'])}}):
        sources=[render_sources.resolve(m,c,gs.probe) for c in doc['clips']]
        for source in sources:
            if digest(source['path'])!=source['sha256']:raise ValueError('Original recording identity changed')
        fps=render_sources.delivery_rate(sources,cfg['fps']);offset=0;visuals=[];speech_inputs=[];speech_filters=[];windows=[];placements=[]
        for i,(c,source) in enumerate(zip(doc['clips'],sources),1):
            source=dict(source,focus_x=c.get('focus_x',.43))
            graph,framing=render_sources.picture_filters(source,cfg,c.get('framing','blur_contain'))
            hold=float(c.get('end_reading_hold',0));display_duration=c['duration']+hold
            graph='setpts=PTS-STARTPTS,'+(f"trim=duration={c['duration']},tpad=stop_mode=clone:stop_duration={hold}," if hold else '')+graph
            source['output_duration']=display_duration
            # Only independently verified exact dialogue is re-typeset. The
            # portrait crop excludes the original lower subtitle UI strip.
            sub=out/f'caption_{i}_dialogue.ass';subtitle_ass(sub,doc['editorial']['dialogue'],c['start'],display_duration,cfg['width'],cfg['height'])
            graph+=f',ass={sub.name}:fontsdir=.'
            spoken_index=next((j for j,(index,_) in enumerate(spoken) if index==i-1),None)
            if spoken_index is not None:
                words=align['lines'][spoken_index]['words'];delay=float(c.get('commentary_start',.08))
                path=Path(voice_folder)/'Voices'/f'line_{spoken_index+1:02d}.wav';duration=gs.duration(path)
                if delay+duration>c['duration']-.05:raise ValueError('Commentary does not fit; existing speech retained')
                if c.get('commentary_before_dialogue'):
                    starts=[line['start']-c['start'] for line in doc['editorial']['dialogue'] if line['start']>=c['start']]
                    if not starts or delay+duration>min(starts)-.15:raise ValueError('Hook overlaps game dialogue reading; retain speech and revise placement')
                cap=out/f'karaoke_{i:02d}.ass';captions.write_ass(cap,words,cfg['width'],cfg['height'],delay);graph+=f',ass={cap.name}:fontsdir=.'
                normalized=out/f'commentary_{i:02d}.wav';gain=audio_pipeline.master_gain(path,cfg['voice_lufs'])
                gs.normalize_voice_exact(path,normalized,duration,cfg,gain_db=gain['gain_db'])
                speech_inputs+=['-i',normalized];j=len(speech_filters);speech_filters.append(f'[{j}:a]adelay={round((offset+delay)*1000)}:all=1[s{j}]')
                windows.append((offset+delay,offset+delay+duration));placements.append(offset+delay)
            if source['fps']>fps:graph+=f',fps={fps}'
            _,visual=render_sources.encode_shot(p,out,i,source,cfg,graph+',format=yuv420p',fps,framing,run,gs.probe,gs.duration)
            visual['final_start']=offset;visuals.append(visual);offset+=display_duration
    samples=round(offset*48000);exact=f'aresample=48000,apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB'
    speech=out/'commentary_timeline.wav'
    if spoken:
        graph=';'.join(speech_filters)+';'+''.join(f'[s{i}]' for i in range(len(spoken)))+f'amix=inputs={len(spoken)}:normalize=0,'+exact+'[a]'
        run(['ffmpeg','-v','error','-nostdin','-y',*speech_inputs,'-filter_complex',graph,'-map','[a]','-c:a','pcm_f32le',speech])
    else:
        run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',offset,'-c:a','pcm_f32le',speech])
    cfg['audio_mix']=dict(cfg.get('audio_mix',{}),ducking=bool(spoken),target_lufs=-16 if spoken else -20)
    gameplay=music_mix.gameplay_stem(sources,out,offset,cfg,run,gs.probe)
    mix,speech_ref,bed,mix_report=music_mix.mix(speech,music,offset,out,cfg,run,cuts=[v['final_start'] for v in visuals[1:]],gameplay=gameplay)
    listing=out/'concat.txt';listing.write_text(''.join(f"file 'shot_{i:02d}.mp4'\n" for i in range(1,len(sources)+1)))
    video=out/'video.mp4';run(['ffmpeg','-v','error','-nostdin','-y','-f','concat','-safe','0','-i',listing,'-c','copy',video])
    candidate=out/'candidate.mp4';run(['ffmpeg','-v','error','-nostdin','-y','-i',video,'-i',mix,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',offset,'-movflags','+faststart',candidate])
    # Legacy media/audio QC remains intact. Narration windows are required for
    # every declared spoken section, and deliberately absent only with no speech.
    if len(windows)!=len(spoken):raise ValueError('Expected speech windows missing')
    q=gs.qc(candidate,speech_ref,bed,windows,offset,out,cfg)
    if any('black_start:' in warning for warning in q['warnings']):q['errors'].append('Black segment detected in final presentation')
    for visual in visuals:
        final=quality_checks.measure_cadence(candidate,visual['final_start'],min(3,visual['duration']),fps,roi=visual['output_roi'])
        check=quality_checks.compare_cadence(visual['source_cadence'],final);visual['final_comparison']=check
        if check['error']:q['errors'].append(check['error'])
    loudness=audio_pipeline.master_gain(candidate,cfg['audio_mix']['target_lufs'],-1.5)
    artifact=indicators(gs.pcm(candidate,out/'artifact_mix.wav'))
    if loudness['input_true_peak_db']>-.9:q['errors'].append('Encoded mix exceeds -0.9 dBTP')
    if artifact['longest_clipped_run']>=3 or artifact['possible_impulse_seconds']:q['errors'].append('Possible audio click/clipping requires repair')
    q.update(status='failed' if q['errors'] else 'technical_pass',input_key=fp,music=music,audio_mix=mix_report,
        encoded_audio_loudness=loudness,final_audio_artifact_indicators=artifact,visual_quality={'scenes':visuals,'proxy_rendering':False},
        editorial_mode=doc['editorial']['mode'],narration_expected=bool(spoken),
        narration_qc='verified real speech windows and word timestamps' if spoken else 'not_applicable_intentionally_no_narration',
        narration_value_requirement='applicable' if spoken else 'not_applicable_intentionally_no_narration',
        captions={'speech':'real word timestamps' if spoken else 'not_applicable_no_speech','source_subtitles':'verified exact text; original onset, readability dwell until next line/clip end; source evidence windows retained separately; not speech timing'},
        source_audio_present=gameplay is not None,character_speech_fabricated=False,cta_timing='optional; not injected')
    save(out/'qc_report.json',q)
    if q['status']!='technical_pass':raise RuntimeError('Final mode-aware QC failed: '+json.dumps(q['errors']))
    final=gs.ROOT/'ReadyForReview'/(p.name+'_dialogue_'+fp[:8]+'.mp4')
    final.parent.mkdir(parents=True,exist_ok=True)
    if final.exists():raise ValueError('Refusing to overwrite a prior preview')
    shutil.copy2(candidate,final);q.update(output=str(final),output_sha256=digest(final));save(p/'qc_report.json',q);save(out/'qc_report.json',q)
    save(p/'dialogue_render_inputs.json',{'voice_folder':str(voice_folder) if voice_folder else None,'expected_spoken_clips':[i for i,_ in spoken]})
    final.with_suffix('.music.txt').write_text(music.get('attribution','')+'\n',encoding='utf-8')
    if spoken:
        captions.sidecars(out,align['lines'],placements)
        shutil.copy2(out/'subtitles.srt',final.with_suffix('.srt'))
        shutil.copy2(out/'caption_timeline.json',final.with_suffix('.captions.json'))
    else:save(final.with_suffix('.captions.json'),{'mode':'visible_source_subtitles','timing':'on-screen frame windows; not speech-word timing','lines':doc['editorial']['dialogue']})
    music_library.commit(p,music,final,fp,cfg['audio_mix'],performance=q)
    return final

def run_project(project):
    import voices,captions
    p=Path(project);doc=read(p/'edit_plan.json');guard(p,doc)
    spoken=[c for c in doc['clips'] if c['narration'].strip()]
    voice=voices.ensure(p,spoken) if spoken else None
    if spoken and not captions._from_saved_heygen_words(voice,spoken):raise ValueError('Real speech alignment unavailable')
    return render(p,voice)
