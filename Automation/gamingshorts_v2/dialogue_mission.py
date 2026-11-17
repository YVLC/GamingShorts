"""Compare three cached events, then produce only independently reviewed moments."""
import json,re,shutil,sqlite3
from pathlib import Path
from common import read,save,key,digest,now,locked,config,run
import gaming_shorts as gs,dialogue_editorial as policy,creative_history,editorial,shared_index
from game_store import GameStore
from game_index import cached_ai,checked_recording

def release():return gs.ROOT/'Releases/2026-11-14-dialogue-editorial'
def existing_mission():return read(gs.ROOT/'Releases/2026-11-13-full-analysis/mission-state.json')
def state_path():return release()/'state.json'

def eligible(scene,store,project=None,review=False):
    if store.eligible(scene,project=project):return True
    # Old automatic 25–40s/action/CTA holds are not user rejections. Reassess
    # them under the new policy without modifying the historical scene record.
    if not str(scene.get('rejected') or '').startswith('Bounded automatic exclusion after definite editorial/evidence rejection'):return False
    if not review:
        path=Path(project)/'dialogue_reassessment.json' if project else None
        if not path or not path.exists():return False
        proof=read(path)
        if scene['id'] not in proof['scene_ids'] or proof['plan_key']!=key(read(Path(project)/'edit_plan.json')):return False
    return store.eligible(dict(scene,rejected=None),project=project)

def select_events(store,r):
    catalog=read(gs.ROOT/'FootageIndex'/('sha256_'+r['sha256'])/'CreativeDiscovery_v2/catalog.json')
    scenes={s['id']:s for s in store.scenes(r['id'])};result=[]
    for name,pattern in [('avalanche',r'avalanche|falling snow'),('crystal',r'crystal'),('birthday',r'birthday')]:
        families=[e for e in catalog['events'] if re.search(pattern,e['premise']+' '+e['central_event'],re.I)]
        candidates=[scenes[i] for e in families for i in e['scene_ids'] if i in scenes and eligible(scenes[i],store,review=True) and scenes[i]['end']-scenes[i]['start']>=8]
        if not candidates:raise ValueError('No eligible existing evidence for comparison target '+name)
        def target_fit(scene):
            physical=bool(re.search(r'cut|chip|polish|strike',scene['description'],re.I)) if name=='crystal' else False
            return (physical,scene['end']-scene['start'],scene['score'])
        scene=max(candidates,key=target_fit)
        a=max(scene['start'],scene['end']-45);b=scene['end']
        result.append({'event_id':name,'scene_id':scene['id'],'start':a,'end':b,'scene':scene,'family':families[0]['premise']})
    return result

def compare(scratch,store,r):
    path=release()/'comparison.json'
    if path.exists():return read(path)
    targets=select_events(store,r);images=[]
    for event in targets:
        cursor=event['start']
        while cursor<event['end']:
            span=min(14,event['end']-cursor)
            images.append(shared_index.dense_proxy(scratch,event['scene'],cursor,span));cursor+=span
    summaries=[{k:e[k] for k in ('event_id','scene_id','start','end','family')}|{'saved_observation':e['scene']['description'],'saved_evidence':e['scene']['evidence']} for e in targets]
    evidence_prompt=('Inspect these three DISTINCT Cairn event candidates BEFORE writing commentary. The source has NO gameplay audio. '
        'Use visible game subtitles, timestamped frames and saved observations as evidence. Do not invent speech, unseen words, intent or outcomes. '
        'Transcribe only readable visible dialogue, retaining original wording and approximate on-screen start/end frame intervals. '
        'Mark uncertainty and incomplete transcript coverage honestly. No audio transcription or speech-word timing is available. '
        'Describe each concrete event and its visible outcome. No proposed narration yet. No tools/commands. Return schema JSON. Events: '+json.dumps(summaries))
    evidence=cached_ai(release(),evidence_prompt,policy.EVIDENCE,images,'dialogue_evidence')
    target_map={e['event_id']:e for e in targets}
    def validate_evidence(result):
        if {e['event_id'] for e in result['events']}!=set(target_map):raise ValueError('All three events must be inspected before comparison')
        for item in result['events']:
            target=target_map[item['event_id']]
            if item['scene_id']!=target['scene_id']:raise ValueError('Dialogue evidence references wrong scene')
            for line in item['dialogue']:
                if not target['start']<=line['start']<line['end']<=target['end']:raise ValueError('Dialogue line outside inspected bounds or zero-duration: '+json.dumps(line))
    try:validate_evidence(evidence)
    except ValueError as error:
        save(release()/'initial_dialogue_validation_failure.json',{'reason':str(error),'response':evidence})
        evidence=cached_ai(release(),evidence_prompt+' A completed response failed bounds validation: '+str(error)+
            '. Correct evidence only. Omit zero-duration/isolated-frame lines whose positive display interval is not established. '
            'Every retained interval must be positive and inside supplied event bounds. Never pad or invent duration/words. Return schema JSON. Prior response: '+json.dumps(evidence),policy.EVIDENCE,images,'dialogue_evidence_correction')
        validate_evidence(evidence)
    save(release()/'dialogue_evidence.json',{'result':evidence,'images':{str(p):digest(p) for p in images},'source_audio_present':False,'ocr_engine':'unavailable; independent visual verification used','timestamp_method':'visible frame windows; not fabricated speech timestamps'})
    history=[{'id':h['id'],'facts':h['facts']} for h in creative_history.history()]
    prompt=('Compare ALL THREE inspected candidates before choosing edits. Produce one proposal for each, or mark it unsuitable. '
        'Goal: compelling self-contained moments, not generic plot summaries or narrated recaps. '
        'Prefer one coherent contiguous 15–25 second sequence. Use less/longer only when it completes the real story; never pad to a target. '
        'Dialogue, visual mystery and physical-action hooks are all valid. End on the actual payoff. CTA is optional; omit generic Subscribe for more. '
        'Modes: narrated only if commentary adds substantial non-obvious context, explanation, contrast or humor; hybrid for a genuinely useful brief hook '
        'then source dialogue; gameplay-first when the scene/subtitles already tell it best. '
        'The source has NO gameplay audio: never invent character voices or pretend source speech can be heard. Faithful visible subtitles and licensed music are allowed. '
        'Reject commentary repeating/paraphrasing visible dialogue, describing obvious actions, or announcing obvious emotions. '
        'The robot recap was specifically rejected by the user for "Now she says, robot, please", narrating the turn-back-on request and apology, ice-wall filler and subscription CTA. Do not repeat that approach. '
        'Choose a single contiguous range within that event scene and inspected bounds. No montage requirement and no minimum three shots. '
        'Supply empty commentary for gameplay-first. Prefer gameplay-first over unnecessary narration. No unsupported claims, fake causal continuity or forced cliffhangers. '
        'Current user narration preference (still subject to nonredundancy/evidence review): '+str(config().get('dialogue_narration_preference','event appropriate'))+'. '
        'No commands/tools. Return schema JSON. Events: '+json.dumps(summaries)+' Dialogue evidence: '+json.dumps(evidence)+' Historical stories and feedback: '+json.dumps(history))
    result=cached_ai(release(),prompt,policy.COMPARISON,images,'compare_editorial_modes')
    if {c['event_id'] for c in result['candidates']}!=set(target_map):raise ValueError('Comparison must account for the three distinct events')
    for choice in result['candidates']:
        event=target_map[choice['event_id']]
        if choice['scene_id']!=event['scene_id'] or not event['start']<=choice['start']<choice['start']+choice['duration']<=event['end']:
            raise ValueError('Proposed edit is outside cached evidence')
    proof={'source_sha256':r['sha256'],'targets':summaries,'evidence':evidence,'comparison':result,'evidence_images':{str(p):digest(p) for p in images},'created_utc':now()}
    save(path,proof);return proof

def exact_images(project,clip):
    images=[shared_index.dense(project,clip['start'],clip['duration'])]
    # A high-resolution original subtitle strip complements the full image.
    # No OCR installation and no character audio are invented.
    folder=Path(project)/'DialogueEvidence';folder.mkdir(exist_ok=True)
    identity=key({'start':clip['start'],'duration':clip['duration'],'source':read(Path(project)/'manifest.json')['source_sha256']})
    dest=folder/(identity+'.jpg');proof=dest.with_suffix('.json')
    if not (dest.exists() and proof.exists() and read(proof)['sha256']==digest(dest)):
        shutil.copyfile(config()['font'],folder/'font.ttf')
        vf=(f"crop=iw:ih*0.30:0:ih*0.68,scale=960:-2,settb=AVTB,setpts=PTS-STARTPTS+{clip['start']:.6f}/TB,"
            "drawtext=fontfile=font.ttf:text='%{pts\\:hms}':fontsize=20:fontcolor=white:box=1:boxcolor=black@0.7:x=4:y=4,"
            f"fps=16/{clip['duration']:.6f},tile=4x4")
        run(['ffmpeg','-v','error','-nostdin','-y','-threads','2','-ss',clip['start'],'-t',clip['duration'],'-i',read(Path(project)/'manifest.json')['source'],
             '-an','-vf',vf,'-frames:v','1','-update','1',dest],cwd=folder,logfile=folder/'frames.log')
        save(proof,{'sha256':digest(dest),'start':clip['start'],'duration':clip['duration']})
    images.append(dest)
    # Tile sampling ends before the exact cut. Verify the last original frame
    # separately so an unobserved tail cannot be mistaken for a known ending.
    ending=folder/(identity+'_ending.jpg')
    if not ending.exists():
        run(['ffmpeg','-v','error','-nostdin','-y','-ss',clip['start']+clip['duration']-.06,'-i',read(Path(project)/'manifest.json')['source'],
             '-vf','scale=1920:-2','-frames:v','1',ending],logfile=folder/'frames.log')
    images.append(ending);return images

def plan_choice(project,choice,comparison):
    p=Path(project);store=GameStore();r=store.recording();scene=next(s for s in store.scenes(r['id']) if s['id']==choice['scene_id'])
    ev=next(e for e in comparison['evidence']['events'] if e['event_id']==choice['event_id'])
    dialogue=[line for line in ev['dialogue'] if line['start']<choice['start']+choice['duration'] and line['end']>choice.get('dialogue_start',choice['start'])]
    selected_evidence=('Only this selected interval is claimed. Visible subtitle evidence: '+
        ' | '.join(line['text'] for line in dialogue)+'. Observed selected ending: '+choice['ending'])
    doc={'editorial':{'policy':policy.VERSION,'mode':choice['mode'],'premise':choice['premise'],'hook':choice['hook'],
        'structure':'discovery_reveal','payoff':choice['ending'],'beats':[choice['hook'],choice['ending']],
        'evidence':selected_evidence,'game_title':'Cairn','cta':False,'dialogue':dialogue,'added_value':choice['added_value'],
        'narrator_role':'external commentator; never Aava or another game character',
        'dialogue_presentation':'The lower original subtitle UI is excluded by dialogue_portrait framing. Only the verified dialogue lines in this plan are re-typeset, at or after their listed onsets. No original audio exists. Introductory commentary finishes before those captions start.' if choice.get('commentary_before_dialogue') else 'Verified visible source dialogue',
        'narration_rationale':choice['narration_rationale'],'duration_reason':choice['duration_reason'],
        },
        'clips':[{'start':choice['start'],'duration':choice['duration'],'scene_id':scene['id'],'narration':choice['commentary'],
            'caption':'','evidence':selected_evidence,'framing':choice.get('framing','blur_contain'),'focus_x':choice.get('focus_x',.43),'commentary_start':.08,'end_reading_hold':choice.get('end_reading_hold',0),'commentary_before_dialogue':choice.get('commentary_before_dialogue',False)}],
        'music':{'mood':choice['mood'],'instrumental_only':not bool(choice.get('music_track_ids',config().get('dialogue_music_track_ids',[]))),
            'track_ids':choice.get('music_track_ids',config().get('dialogue_music_track_ids',[]))}}
    doc['editorial']['dialogue_caption_schedule']=policy.presentation_windows(dialogue,choice['start'],choice['duration']+choice.get('end_reading_hold',0))
    policy.validate(doc,read(p/'manifest.json'))
    images=exact_images(p,doc['clips'][0])
    prompt=('Independently review this proposed Short against actual original frames and subtitle strip, not just the proposed text. '
        'Check immediate curiosity OR dialogue/visual mystery (physical action is NOT mandatory), natural pacing, emotion/comedy, clear self-contained event, '
        'nonredundant commentary, truthful subtitles and added value, chronology, no unnecessary cuts or static filler, and a satisfying real ending. '
        'A continuous scene is one event, not several clips/events. No forced montage, target duration or subscription CTA. '
        'The recording has NO source audio. Never approve invented character speech. Gameplay-first requires no AI narration and may use verified visible subtitles plus music. '
        'For narrated/hybrid, compare commentary literally AND semantically against every visible subtitle and obvious action/emotion: recap/paraphrase is a rejection. '
        'Humor, an external commentator perspective, and clearly figurative comic contrasts may add value without new lore. Do not misattribute a narrator joke to a game character or invent gameplay facts to support it. '
        'Evaluate the actual declared subtitle presentation: dialogue_portrait excludes the original lower subtitle UI, so omitted source-text lines do not compete with narration in the output. The rendered crop must still pass final review. '
        'For legibility use dialogue_caption_schedule (actual output-relative caption display intervals), not dialogue source observation windows. The latter record evidence only and do not prescribe caption disappearance. The actual renderer uses this same bounded dwell schedule, never anticipates a line, and stops it before the next line. '
        'For gameplay-first, nonredundancy/value flags can be true because unnecessary narration is intentionally absent; assess whether the original scene is compelling. '
        'Faithful visible dialogue lines will be enlarged for readability; the specified source-aware portrait framing is independently checked after render. Verify their exact words against the original subtitle strip. '
        'Any uncertain/inaccurate line must fail dialogue_faithful; do not fabricate missing words. Set issues only for actual defects, cite evidence, and reject uncertainty. '
        'All flags and score >=.85 with no issues are mandatory. No tools. Return schema JSON. Plan: '+json.dumps(doc)+' Source dialogue evidence: '+json.dumps(ev))
    review=cached_ai(p/'DialogueQuality',prompt,policy.REVIEW,images,'editorial_quality')
    save(p/'dialogue_editorial_review.json',{'plan_key':key(doc),'source_sha256':r['sha256'],'review':review,'evidence_images':{str(x):digest(x) for x in images}})
    if not policy.review_passes(review,choice['mode']):
        save(p/'dialogue_quality_rejection.json',{'plan':doc,'review':review});raise ValueError('Dialogue/storytelling review rejected candidate: '+json.dumps(review['issues']))
    creative_history.require_review(p,doc,invoke=True,images=images)
    # Reassessment is explicit and scoped to this newly reviewed plan. Historical
    # rejection metadata stays unchanged in SQLite.
    save(p/'dialogue_reassessment.json',{'plan_key':key(doc),'scene_ids':[scene['id']],
        'old_automatic_hold':scene['rejected'],'new_policy_review_passed':True,'updated_utc':now()})
    approved_scene=dict(scene,rejected=None) if str(scene.get('rejected') or '').startswith('Bounded automatic exclusion after definite editorial/evidence rejection') else scene
    store.reserve(p,doc,[approved_scene])
    save(p/'edit_plan.json',doc);editorial.remember(p)
    policy.guard(p,doc)
    return doc

def plan_next(project):
    p=Path(project);comparison=read(release()/'comparison.json');store=GameStore()
    for choice in comparison['comparison']['candidates']:
        scene=next(s for s in store.scenes(store.recording()['id']) if s['id']==choice['scene_id'])
        if choice['suitable'] and eligible(scene,store,review=True):return plan_choice(p,choice,comparison)
    raise ValueError('No independently usable dialogue-mode candidate remains')

def report(state):
    parent=existing_mission();dest=Path(parent['review_folder']);save(dest/'DIALOGUE_EDITORIAL_REPORT.json',state)
    if parent.get('error') or parent.get('traceback'):
        parent.setdefault('previous_controller_failure',{'error':parent.get('error'),'traceback':parent.get('traceback')})
        parent.pop('error',None);parent.pop('traceback',None)
    parent.update(editorial_revision=policy.VERSION,revision_state=str(state_path()),stage='dialogue_editorial:'+state['stage'],dialogue_outputs=state.get('outputs',[]),updated_utc=now())
    for old in parent.get('outputs',[]):
        if 'af978f310d6b3fbcb224' in old.get('project',''):old.update(editorial_status='user_rejected',counts_toward_current_delivery=False)
    save(gs.ROOT/'Releases/2026-11-13-full-analysis/mission-state.json',parent)
    lines=['# Cairn — dialogue and storytelling repair','', 'Updated: '+now(),'Mission: '+state['mission_id'],'Stage: '+state['stage'],'',
        'The robot recap remains preserved and is recorded as rejected by the user. Nothing is published.','',
        '| Event | Mode | Why this mode | Source range | Editorial review | Independent originality | Render / QC | Preview |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for item in state.get('candidates',[]):
        a=item.get('start',0);b=a+item.get('duration',0)
        def ts(n):return f'{int(n//3600):02}:{int(n%3600//60):02}:{n%60:06.3f}'
        lines.append('| '+' | '.join(str(x).replace('|','/') for x in (item.get('event_id'),item.get('mode'),item.get('narration_rationale'),ts(a)+'–'+ts(b),item.get('quality','pending'),item.get('originality','pending'),item.get('status','pending'),item.get('preview','not available')))+' |')
        if item.get('error'):lines+=['','Held: '+str(item['error'])]
    lines+=['','Comparison of all three events is retained in `Releases/2026-11-14-dialogue-editorial/comparison.json`.',
        'Unvoiced previews preserve visible source subtitles and contain no fabricated character speech. Enlarged subtitle lines use verified on-screen frame-window timing, not fictional speech/word timestamps.',
        'Narrated/hybrid sections require real word timestamps and speech-presence/correlation checks. Technical QC and human editorial approval remain separate.']
    (dest/'DIALOGUE_EDITORIAL_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(state_path(),state)

def continue_mission():
    from start import prepare
    from job_store import JobStore
    root=gs.ROOT;release().mkdir(exist_ok=True);store=GameStore();r=store.recording();parent=existing_mission()
    state=read(state_path()) if state_path().exists() else {'mission_id':parent['mission_id'],'revision':policy.VERSION,'stage':'comparing_events','candidates':[],'outputs':[]}
    with locked(root/'Database/.full_analysis_mission.lock'),locked(root/'Database/.workflow_v2.lock'):
        checked_recording(r);creative_history.refresh()
        proof=JobStore(root).admit_source(r['source'])
        scratch=prepare(Path(r['source']),'dialogue_evidence_'+parent['mission_id'],verified_source=proof,full_game_context={'recording':r['id'],'index_key':r['index_key'],'game':r['game'],'batch':'dialogue_evidence'})
        report(state);comparison=compare(scratch,store,r)
        save(release()/'comparison-summary.json',comparison['comparison'])
        if not state['candidates']:state['candidates']=[dict(c,status='not queued',quality='pending',originality='pending') for c in comparison['comparison']['candidates']]
        state['stage']='producing_review_previews';report(state)
        for item in state['candidates']:
            if item.get('status') in ('technical_pass','held'):continue
            if not item['suitable']:item.update(status='held',error=item['reason']);report(state);continue
            identity='dlg_'+key({'mission':state['mission_id'],'event':item['event_id'],'policy':policy.VERSION})[:16]
            with store.connect() as db:db.execute("INSERT OR IGNORE INTO game_batches VALUES (?,?,?,?,?,'planning',NULL,?)",(identity,r['game'],r['id'],r['index_key'],1,now()))
            p=prepare(Path(r['source']),identity,verified_source=proof,full_game_context={'recording':r['id'],'index_key':r['index_key'],'game':r['game'],'batch':identity})
            with store.connect() as db:db.execute('INSERT OR IGNORE INTO game_batch_items VALUES (?,?,?,?,NULL)',(identity,0,str(p),'{}'))
            item['project']=str(p)
            try:
                changed_framing=(p/'edit_plan.json').exists() and any(read(p/'edit_plan.json')['clips'][0].get(k,default)!=item.get(k,default) for k,default in (('framing','blur_contain'),('duration',0),('end_reading_hold',0),('focus_x',.43)))
                if not (p/'edit_plan.json').exists() or changed_framing:plan_choice(p,item,comparison)
                else:
                    accepted=read(p/'edit_plan.json')
                    images=exact_images(p,accepted['clips'][0])
                    # Cached proofs return without a call; changed history or
                    # reviewer policy requires a current independent verdict.
                    creative_history.require_review(p,accepted,invoke=True,images=images)
                item.update(quality='passed',originality='passed',status='rendering');report(state)
                with store.connect() as db:db.execute("UPDATE game_batches SET status='planned',error=NULL WHERE id=?",(identity,))
                final=policy.run_project(p)
                # Review the actual portrait presentation, not only its source.
                q=read(p/'qc_report.json')
                portrait_frames=[Path(q['review_sheet'])]
                frame_folder=p/'Renders'/q['input_key'][:16]
                for n,t in enumerate((.5,q['actual_duration']*.55,max(.5,q['actual_duration']-.75))):
                    image=frame_folder/f'portrait_full_{n}.jpg'
                    if not image.exists():run(['ffmpeg','-v','error','-nostdin','-y','-ss',t,'-i',final,'-frames:v','1',image])
                    portrait_frames.append(image)
                final_doc=read(p/'edit_plan.json')
                verified={'actual_duration':q['actual_duration'],'source_timeline':[(c['start'],c['duration']) for c in final_doc['clips']],
                    'continuous_single_shot':len(final_doc['clips'])==1,'subtitle_frame_windows':final_doc['editorial']['dialogue'],
                    'subtitle_presentation_windows':[policy.presentation_windows(final_doc['editorial']['dialogue'],c['start'],c['duration']+c.get('end_reading_hold',0)) for c in final_doc['clips']],
                    'intentional_final_reading_hold':final_doc['clips'][-1].get('end_reading_hold',0),
                    'subtitle_presentation_policy':'Exact verified source text, never shown before its original onset. Readability dwell may continue into a gap, until next line/clip end; evidence windows remain unmodified. Original subtitle UI strip excluded to avoid duplicate text.',
                    'narration_expected':q['narration_expected'],'source_audio_present':q['source_audio_present'],
                    'character_speech_fabricated':False,'full_decode_and_audio_qc':q['status']}
                prompt=('Independently assess these ACTUAL rendered portrait frames, including full-size frames for legibility. '
                    'Check scene visibility, faithful readable subtitles, clarity, curiosity/dialogue hook, natural pacing and a complete ending. '
                    'Dialogue and visual-mystery hooks are allowed; physical action is not mandatory. A dialogue punchline is a valid payoff. '
                    'Source has no audio. Audio lineage and exact source/caption timing are provided by validated renderer metadata; do not pretend to listen or infer unrecorded performance. '
                    'Use those timing facts rather than guessing dwell/cuts from sparse thumbnails. Report only ACTUAL defects as issues; describe limits in reason. '
                    'For gameplay-first there is intentionally NO commentary: narration_adds_value is NOT APPLICABLE, and lack of narration must not lower the visual/story score. '
                    'All actual visual/storytelling criteria, score >=.85 and no unresolved issues are still required. No tools. Plan: '+json.dumps(final_doc)+' Verified metadata: '+json.dumps(verified))
                final_review=cached_ai(p/'DialogueQuality',prompt,policy.REVIEW,portrait_frames,'portrait_editorial_review')
                save(p/'portrait_editorial_review.json',final_review)
                if not policy.review_passes(final_review,final_doc['editorial']['mode']):raise ValueError('Final portrait editorial review held: '+json.dumps(final_review['issues']))
                if not policy.completed(p):raise ValueError('Render inputs changed after QC; retain the draft and revalidate')
                target=Path(parent['review_folder'])/'dialogue_editorial_v1'/final.name;target.parent.mkdir(exist_ok=True)
                if target.exists() and digest(target)!=digest(final):raise ValueError('Refusing to overwrite an existing preview')
                if not target.exists():shutil.copy2(final,target)
                for suffix in ('.music.txt','.captions.json','.srt'):
                    sidecar=final.with_suffix(suffix)
                    if sidecar.exists() and not target.with_suffix(suffix).exists():shutil.copy2(sidecar,target.with_suffix(suffix))
                item.update(status='technical_pass',preview=str(target),duration=q['actual_duration'],qc=str(p/'qc_report.json'))
                state['outputs'].append({'event_id':item['event_id'],'path':str(target),'sha256':digest(target)})
                with store.connect() as db:db.execute("UPDATE game_batches SET status='ready_for_review' WHERE id=?",(identity,))
                editorial.remember(p,'validated')
            except Exception as error:
                item.update(status='held',error=str(error))
                with store.connect() as db:db.execute("UPDATE game_batches SET status='needs_attention',error=? WHERE id=?",(str(error),identity))
            report(state)
        state['stage']='complete' if len(state['outputs'])==3 else 'complete_valid_candidates_only';report(state)
