"""Same two Cairn events: user-requested spoken hooks and existing cleared songs.
No new index, no uncertain voice retries, no publishing, no prior preview overwrite.
"""
import sys,json,shutil,sqlite3,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,key,digest,locked,run,config
import gaming_shorts as gs,dialogue_mission as mission,dialogue_editorial as policy,editorial,music_library
from game_store import GameStore
from game_index import cached_ai,checked_recording

release=gs.ROOT/'Releases/2026-11-14-hybrid-hooks';release.mkdir(exist_ok=True)
statefile=release/'state.json';parent=mission.existing_mission()
destination=Path(parent['review_folder'])/'hybrid_hooks_v1';destination.mkdir(exist_ok=True)

def report(state):
    save(statefile,state);save(destination/'REVIEW_REPORT.json',state)
    lines=['# Cairn — spoken hooks and existing music','',f"Updated: {now()}",'',
        'Same two events, revised at the user’s request. Previous gameplay-first previews are preserved. No publishing.','',
        '| Event | Status | Narration | Original source interval | Preview |','| --- | --- | --- | --- | --- |']
    for item in state['items']:
        c=item['choice'];path=item.get('preview');win=('D:/GamingShorts/'+path.removeprefix('/mnt/d/GamingShorts/')) if path else None
        lines.append('| '+' | '.join([item['event'],item['status'],c['commentary'],f"{c['start']}–{c['start']+c['duration']} seconds",f'[Open](<{win}>)' if win else 'pending'])+' |')
        if item.get('error'):lines+=['','Blocked: '+item['error']]
        if item.get('qc'):lines+=['',json.dumps(item['qc'],ensure_ascii=False)]
    lines+=['','Narration is commentary, never recreated character speech. Actual speech word timestamps drive the existing yellow highlights. Source dialogue follows without overlapping narration. Music uses cleared original local song files and retained attribution; inferred excerpts are not labeled verified trends.']
    (destination/'REVIEW_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    store=GameStore();recording=store.recording();checked_recording(recording)
    if not (release/'before.sqlite3').exists():
        with store.connect() as db,sqlite3.connect(release/'before.sqlite3') as backup:db.backup(backup)
    if statefile.exists():state=read(statefile)
    else:
        previous=read(mission.state_path());comparison=read(mission.release()/'comparison.json');items=[];images=[]
        tracks={t['id']:t for t in music_library.catalog()}
        allowed=config()['dialogue_music_track_ids']
        if any(i not in tracks for i in allowed):raise ValueError('Requested local music failed existing clearance checks')
        for old in previous['candidates']:
            if old['event_id'] not in ('crystal','birthday'):continue
            p=Path(old['project']);doc=read(p/'edit_plan.json');c=doc['clips'][0]
            archive=p/'EditorialRevisions'/'before_hybrid_hooks_v1';archive.mkdir(exist_ok=True,parents=True)
            for file in p.glob('*.json'):
                if not (archive/file.name).exists():shutil.copy2(file,archive/file.name)
            choice=next(dict(x) for x in comparison['comparison']['candidates'] if x['event_id']==old['event_id'])
            choice.update(start=c['start']-5,duration=c['duration']+5,dialogue_start=c['start'],mode='hybrid',commentary_before_dialogue=True,
                music_track_ids=['ncs_royalty_regular' if old['event_id']=='crystal' else 'ncs_inmyhead_regular'],
                duration_reason='Five contiguous original-source seconds introduce a brief added-value spoken hook; the previously verified dialogue setup and payoff follow. The final 1.5-second reading hold is retained.',end_reading_hold=1.5)
            images+=mission.exact_images(p,dict(c,start=choice['start'],duration=choice['duration']))
            items.append({'event':old['event_id'],'project':str(p),'choice':choice,'status':'planning','previous_preview':old['preview']})
        schema=editorial.obj({'hooks':{'type':'array','minItems':2,'maxItems':2,'items':editorial.obj({'event':{'type':'string','enum':['crystal','birthday']},'commentary':editorial.S,'added_value':editorial.S,'rationale':editorial.S})}})
        prompt=('User explicitly requests the existing Garret TTS and yellow word highlights, followed by game dialogue, for these two already selected Cairn moments. '
            'Write ONE excellent short spoken hook for each, 6–10 words, fitting the five-second source lead-in. '
            'Add a humorous or insightful perspective, not a recap or paraphrase of the subtitles, obvious action, or obvious emotion. '
            'Do not pretend original game audio exists. No unsupported lore, invented outcomes, or forced cliffhanger/CTA. '
            'Crystal: contrast glowing treasure-like surroundings with burial ethics; birthday: contrast a warm celebration with being absent, without repeating the actual punchline. '
            'Hooks are commentary, not character speech. Exact selected dialogue and visible original evidence: '+json.dumps(comparison['evidence'])+
            ' Proposed continuous ranges and source frame sheets: '+json.dumps([i['choice'] for i in items])+'. No tools. Return schema JSON.')
        hooks=cached_ai(release,prompt,schema,images,'value_adding_hooks')
        if {h['event'] for h in hooks['hooks']}!={'crystal','birthday'}:raise ValueError('Two distinct event hooks required')
        for item in items:
            hook=next(h for h in hooks['hooks'] if h['event']==item['event'])
            if not 6<=len(hook['commentary'].split())<=10:raise ValueError('Hook length outside brief lead-in budget')
            item['choice'].update(commentary=hook['commentary'],added_value=hook['added_value'],narration_rationale=hook['rationale'])
        state={'mission_id':parent['mission_id'],'revision':'hybrid_hooks_v1','created_utc':now(),'items':items}
        save(release/'comparison_before_revision.json',comparison)
        report(state)
    comparison=read(mission.release()/'comparison.json')
    for item in state['items']:
        if item['status'] in ('ready_for_review','blocked'):continue
        p=Path(item['project']);choice=item['choice']
        try:
            item['status']='editorial_review';report(state)
            expected=key(choice);accepted=p/'hybrid_choice_checkpoint.json'
            if not accepted.exists() or read(accepted)['choice_key']!=expected:
                mission.plan_choice(p,choice,comparison)
                save(accepted,{'choice_key':expected,'plan_key':key(read(p/'edit_plan.json'))})
            doc=read(p/'edit_plan.json')
            # Preflight requested song licensing before any speech call.
            selected=music_library.select(p)
            if selected['id'] not in choice['music_track_ids']:raise ValueError('Requested local song not selected')
            item['status']='speech_and_render';report(state)
            final=policy.run_project(p);q=read(p/'qc_report.json');folder=Path(q['review_sheet']).parent
            frames=[Path(q['review_sheet'])]
            for n,t in enumerate((1.2,8,q['actual_duration']-2)):
                image=folder/f'hybrid_review_{n}.jpg'
                if not image.exists():run(['ffmpeg','-v','error','-nostdin','-y','-ss',t,'-i',final,'-frames:v','1',image])
                frames.append(image)
            prompt=('Independent final editorial check of actual hybrid portrait frames. Brief commentary adds value and must not paraphrase dialogue or fabricate speech. '
                'Check legibility of yellow active-word captions and subsequent faithful dialogue, clear face/scene framing, chronological continuous scene, real payoff, no CTA. '
                'Use saved verified speech placement and source-dialogue timing, not guessed thumbnail dwell. No original gameplay audio exists; actual Garret narration and cleared music are separately verified by technical QC. '
                'Do not pretend to listen. Only actual defects in issues. Plan: '+json.dumps(doc)+' Technical QC: '+json.dumps({k:q[k] for k in ('status','audio_windows','captions','actual_duration','narration_expected','source_audio_present')}))
            verdict=cached_ai(p/'DialogueQuality',prompt,policy.REVIEW,frames,'hybrid_final_review')
            save(p/'hybrid_final_review.json',verdict)
            if not policy.review_passes(verdict,'hybrid'):raise ValueError('Final editorial hold: '+json.dumps(verdict['issues']))
            if not policy.completed(p):raise ValueError('Render changed after checks')
            target=destination/final.name
            if target.exists() and digest(target)!=digest(final):raise ValueError('Prior preview would be overwritten')
            if not target.exists():shutil.copy2(final,target)
            for ext in ('.music.txt','.srt','.captions.json'):
                side=final.with_suffix(ext)
                if side.exists() and not target.with_suffix(ext).exists():shutil.copy2(side,target.with_suffix(ext))
            item.update(status='ready_for_review',preview=str(target),qc={'duration':q['actual_duration'],'technical':q['status'],'editorial_score':verdict['score'],'music':q['music']['title'],'music_segment':q['music'].get('segment'),'errors':q['errors'],'warnings':q['warnings'],'narration':choice['commentary']})
            editorial.remember(p,'validated')
        except Exception as error:item.update(status='blocked',error=str(error))
        report(state)
    state['finished_utc']=now();report(state)
    print(json.dumps({'report':str(destination/'REVIEW_REPORT.md'),'items':[{k:v for k,v in i.items() if k in ('event','status','preview','error')} for i in state['items']]},indent=2))
