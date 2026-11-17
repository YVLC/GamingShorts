"""Explicit user-requested Garret readings; preserve source, hooks and prior exports.

Uses saved free speech results only. Never requests speech or publishes.
"""
import sys, json, re, shutil, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read, save, digest, key, config, run, locked
import gaming_shorts as gs
import captions, dialogue_editorial as policy, render_sources, music_mix, audio_pipeline
import quality_checks

RELEASE=gs.ROOT/'Releases/2026-11-14-dialogue-readaloud'
DEST=gs.ROOT/'ReadyForReview/cairn_first_three_1b28a5dd9e1b/dialogue_readaloud_v1'
PROJECTS={'crystal':'videoplayback_e772d2c8_dlg_91f9ff2ff828ed63',
          'birthday':'videoplayback_e772d2c8_dlg_ec295913de3b30c6'}

def reading_segments(lines, words):
    """Match every exact verified line, retaining real returned word timing."""
    script=' '.join(x['text'] for x in lines)
    captions.validate_words(words,script,max(w['end'] for w in words)+.1)
    result=[];index=0
    for line in lines:
        count=len(captions.tokens(line['text']));chunk=words[index:index+count];index+=count
        # Preserve approved punctuation rather than dropping it in captions.
        tokens=re.findall(r"[\w]+(?:['’][\w]+)*[.,!?;:]*",line['text'])
        if len(tokens)!=count:raise ValueError('Ambiguous caption tokenization')
        chunk=[dict(w,word=t) for w,t in zip(chunk,tokens)]
        result.append(dict(line,words=chunk))
    if index!=len(words):raise ValueError('Unconsumed speech words')
    return result

def place_readings(lines, source_start, hook_end):
    result=[];previous=hook_end
    for line in lines:
        # No line is read ahead of its verified source onset. Overflow shifts
        # following readings; it never cuts speech or changes its speed.
        a=max(line['start']-source_start,previous+.10)
        lo=line['words'][0]['start'];hi=line['words'][-1]['end']
        result.append(dict(line,placement=a,cut_start=max(0,lo-.035),cut_end=hi+.035))
        previous=a+hi-lo+.07
    return result

def render(event):
    p=gs.ROOT/'Projects/V2'/PROJECTS[event];doc=read(p/'edit_plan.json')
    # This is an explicitly requested revision of the same delivered footage,
    # not a new story. Pin its accepted plan/source/evidence and original export;
    # later unrelated history additions cannot invalidate that revision identity.
    m=read(p/'manifest.json');policy.validate(doc,m)
    accepted=read(p/'dialogue_editorial_review.json');old=read(p/'qc_report.json')
    if accepted['plan_key']!=key(doc) or not policy.review_passes(accepted['review'],'hybrid'):raise ValueError('Accepted plan changed')
    if old['status']!='technical_pass' or digest(old['output'])!=old['output_sha256']:raise ValueError('Prior export changed')
    if any(digest(name)!=sha for name,sha in accepted['evidence_images'].items()):raise ValueError('Source evidence changed')
    from game_store import GameStore
    from game_index import checked_recording,verify_integrity
    recording=GameStore().recording(m['full_game']['recording']);checked_recording(recording);verify_integrity(recording)
    if m['source']!=recording['source'] or m['source_sha256']!=recording['sha256']:raise ValueError('Source identity changed')
    cfg=dict(config());clip=doc['clips'][0]
    raw=read(RELEASE/f'{event}_speech.json')
    words=[dict(word=w['text'],start=w['start_time'],end=w['end_time']) for w in raw['original_words']]
    lines=reading_segments(doc['editorial']['dialogue'],words)
    voice=Path(read(p/'dialogue_render_inputs.json')['voice_folder'])
    proof=read(voice/'provenance.json')
    if proof['request']['voice_id']!=cfg['voice_id'] or proof['request']['model']!='heygen-voice-1-turbo-free':raise ValueError('Unexpected hook voice')
    hook=voice/'Voices/line_01.wav'
    if digest(hook)!=proof['files']['line_01.wav']:raise ValueError('Hook checksum changed')
    hook_align=captions._from_saved_heygen_words(voice,[clip])
    hook_delay=float(clip.get('commentary_start',.08));hook_duration=gs.duration(hook)
    scheduled=place_readings(lines,clip['start'],hook_delay+hook_duration)
    end=scheduled[-1]['placement']+scheduled[-1]['cut_end']-scheduled[-1]['cut_start']+.2
    total=max(clip['duration']+clip.get('end_reading_hold',0),end)
    if total-clip['duration']>2:raise ValueError('Reading requires a longer source edit, not an excessive freeze')
    music=read(p/'music_selection.json')
    if digest(music['path'])!=music['sha256']:raise ValueError('Music bytes changed')
    fp=key(dict(code=digest(__file__),captions=digest(captions.__file__),renderer=digest(render_sources.__file__),
                plan=doc,hook=digest(hook),speech=raw,music=music,config=cfg,font=digest(cfg['font'])))
    out=RELEASE/event/fp[:16];out.mkdir(parents=True,exist_ok=True);DEST.mkdir(parents=True,exist_ok=True)
    final=DEST/f'{event}_full_dialogue_{fp[:8]}.mp4'
    if final.exists():
        q=read(out/'qc_report.json')
        if q['status']=='technical_pass' and digest(final)==q['output_sha256']:return q
        raise ValueError('Existing output failed verification; preserve for investigation')
    master=out/'dialogue_original.wav'
    if not master.exists():urllib.request.urlretrieve(raw['audio_url'],master)
    if abs(gs.duration(master)-raw['duration'])>.1:raise ValueError('Speech duration mismatch')
    captions.validate_words(words,' '.join(l['text'] for l in lines),gs.duration(master))
    save(out/'speech_provenance.json',dict(voice_id=cfg['voice_id'],model='heygen-voice-1-turbo-free',
        script=[l['text'] for l in lines],audio_sha256=digest(master),returned_result=raw,
        role='User-requested narrator reading verified text; not original game character audio'))
    inputs=[];filters=[];windows=[];all_words=[];caption_lines=[];placements=[]
    assets=[dict(path=hook,cut_start=0,cut_end=hook_duration,placement=hook_delay,
                 words=hook_align['lines'][0]['words'])]
    for n,line in enumerate(scheduled):
        part=out/f'reading_{n+1:02d}.wav'
        run(['ffmpeg','-v','error','-nostdin','-y','-ss',line['cut_start'],'-i',master,'-t',line['cut_end']-line['cut_start'],'-c:a','pcm_f32le',part])
        assets.append(dict(line,path=part,words=[dict(w,start=w['start']-line['cut_start'],end=w['end']-line['cut_start']) for w in line['words']]))
    for n,asset in enumerate(assets):
        normalized=out/f'normalized_{n:02d}.wav';duration=gs.duration(asset['path'])
        # A one-word utterance is too short for integrated loudness measurement.
        # Derive one shared gain from the original continuous dialogue recording.
        gain=audio_pipeline.master_gain(hook if n==0 else master,cfg['voice_lufs'])
        gs.normalize_voice_exact(asset['path'],normalized,duration,cfg,gain_db=gain['gain_db'])
        inputs+=['-i',normalized];filters.append(f'[{n}:a]adelay={round(asset["placement"]*1000)}:all=1[a{n}]')
        windows.append((asset['placement'],asset['placement']+duration))
        all_words.extend(dict(w,start=w['start']+asset['placement'],end=w['end']+asset['placement']) for w in asset['words'])
        caption_lines.append({'words':asset['words']});placements.append(asset['placement'])
    captions.validate_words(all_words,clip['narration']+' '+' '.join(l['text'] for l in lines),total)
    captions.write_ass(out/'full_reading.ass',all_words,cfg['width'],cfg['height'])
    captions.sidecars(out,caption_lines,placements)
    samples=round(total*48000);speech=out/'speech_timeline.wav'
    graph=';'.join(filters)+';'+''.join(f'[a{n}]' for n in range(len(assets)))+f'amix=inputs={len(assets)}:normalize=0,aresample=48000,apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB[a]'
    run(['ffmpeg','-v','error','-nostdin','-y',*inputs,'-filter_complex',graph,'-map','[a]','-c:a','pcm_f32le',speech])
    source=render_sources.resolve(m,clip,gs.probe);source.update(focus_x=clip.get('focus_x',.43),output_duration=total)
    picture,framing=render_sources.picture_filters(source,cfg,clip['framing'])
    hold=total-clip['duration'];fps=render_sources.delivery_rate([source],cfg['fps'])
    graph=f"setpts=PTS-STARTPTS,trim=duration={clip['duration']},tpad=stop_mode=clone:stop_duration={hold},"+picture+',ass=full_reading.ass:fontsdir=.,format=yuv420p'
    shutil.copy2(cfg['font'],out/'font.ttf')
    _,visual=render_sources.encode_shot(p,out,1,source,cfg,graph,fps,framing,run,gs.probe,gs.duration)
    cfg['audio_mix']=dict(cfg.get('audio_mix',{}),ducking=True,target_lufs=-16)
    mix,ref,bed,mix_report=music_mix.mix(speech,music,total,out,cfg,run,cuts=[])
    candidate=out/'candidate.mp4'
    run(['ffmpeg','-v','error','-nostdin','-y','-i',out/'shot_01.mp4','-i',mix,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',total,'-movflags','+faststart',candidate])
    q=gs.qc(candidate,ref,bed,windows,total,out,cfg)
    cadence=quality_checks.measure_cadence(candidate,0,min(3,clip['duration']),fps,roi=visual['output_roi'])
    check=quality_checks.compare_cadence(visual['source_cadence'],cadence)
    if check['error']:q['errors'].append(check['error'])
    from audio_checks import indicators
    artifacts=indicators(gs.pcm(candidate,out/'artifact.wav'))
    loudness=audio_pipeline.master_gain(candidate,-16,-1.5)
    if artifacts['longest_clipped_run']>=3 or artifacts['possible_impulse_seconds']:q['errors'].append('Audio clipping or impulse')
    if loudness['input_true_peak_db']>-.9:q['errors'].append('Excessive audio true peak')
    if any('black_start:' in w for w in q['warnings']):q['errors'].append('Black frames')
    q.update(status='failed' if q['errors'] else 'technical_pass',event=event,input_key=fp,
             reading_schedule=scheduled,spoken_sections=len(assets),caption_words=len(all_words),
             final_spoken_word_end=all_words[-1]['end'],visual_quality=visual,cadence_check=check,
             audio_artifacts=artifacts,loudness=loudness,audio_mix=mix_report,
             source_interval=[clip['start'],clip['start']+clip['duration']],reading_hold=hold,
             listening_review='not_performed',editorial_review='human review required')
    save(out/'qc_report.json',q)
    if q['errors']:raise ValueError(q['errors'])
    shutil.copy2(candidate,final)
    for name,ext in [('subtitles.srt','.srt'),('caption_timeline.json','.captions.json')]:shutil.copy2(out/name,final.with_suffix(ext))
    final.with_suffix('.music.txt').write_text(music.get('attribution','')+'\n',encoding='utf-8')
    q.update(output=str(final),output_sha256=digest(final));save(out/'qc_report.json',q)
    return q

def main():
    results=[]
    with locked(gs.ROOT/'Database/.workflow_v2.lock'):
        for event in PROJECTS:
            print('Rendering '+event,flush=True);q=render(event);results.append(q)
            save(RELEASE/'delivery.json',results)
            print(json.dumps({k:q[k] for k in ('event','status','output','spoken_sections','final_spoken_word_end','actual_duration')}),flush=True)
    lines=['# Cairn: complete spoken dialogue with yellow word highlights','',
           'Garret reads the existing opening and every verified game dialogue line. The source recording is silent; these are narrator readings requested by the user. Earlier previews remain preserved.','']
    for q in results:
        path=q['output'].replace('/mnt/d/','D:/')
        lines.append(f"- [{q['event'].title()}](<{path}>): {q['actual_duration']:.2f}s; {q['spoken_sections']} spoken sections; technical QC {q['status']}.")
    lines+=['','Speech audio and word timestamps are preserved from the free Garret model. No speech speed change. Existing music and attribution retained. Full decode, every spoken section, voice/music balance, audio correlation, cadence and clipping checks passed. Listening and editorial review have not been performed. No publishing.']
    (DEST/'REVIEW_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':main()
