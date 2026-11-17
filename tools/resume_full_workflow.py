"""Authorized full-recording mission. Pilot -> local-first index -> up to 3 unique
single-item batches through existing gates. No uploader, TTS retry, or source copy.
"""
from pathlib import Path
import sys,json,sqlite3,shutil,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked,digest
import gaming_shorts as gs
import local_index
from game_store import GameStore
import full_game,game_plan

ROOT=gs.ROOT
EVIDENCE=ROOT/'Releases/2026-11-13-full-analysis'
STATE=EVIDENCE/'mission-state.json'

def write(state,stage,error=None):
    state.update(stage=stage,updated_utc=now())
    if error:state['error']=str(error)
    save(STATE,state)
    dest=Path(state['review_folder']);dest.mkdir(parents=True,exist_ok=True)
    save(dest/'review-report.json',state)
    lines=['# Cairn full-recording mission', '', 'Stage: '+stage, '', 'Analysis: '+str(EVIDENCE/'progress.json'), '', 'Valid delivered Shorts: '+str(len(state['outputs'])), '']
    if state.get('error'):lines+=['Attention: '+state['error'],'']
    for item in state['outputs']:
        lines += ['## '+item['title'],'', 'File: '+item['output'],'','Source ranges: '+json.dumps(item['ranges']),'','Narrative: '+item['summary'],'','Spoiler: '+item['spoiler'],'QA: '+item['qa'],'']
    (dest/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')

def batch_ids(store):
    with store.connect() as db:return [r[0] for r in db.execute('SELECT id FROM game_batches')]

def deliver(batch,state):
    for item in batch['items']:
        p=Path(item['project']);qpath=p/'qc_report.json'
        if not qpath.exists():continue
        q=read(qpath)
        if q.get('status')!='technical_pass' or not Path(q.get('output','')).is_file():continue
        final=Path(q['output'])
        if digest(final)!=q['output_sha256']:raise ValueError('Final output changed after QC')
        if any(x['project']==str(p) for x in state['outputs']):continue
        if not gs.completed(p):raise ValueError('Plan, narration or render identity changed since technical QC')
        doc=read(p/'edit_plan.json')
        dest=Path(state['review_folder'])/final.name
        if dest.exists() and digest(dest)!=q['output_sha256']:raise ValueError('Refusing to overwrite review video')
        if not dest.exists():shutil.copy2(final,dest)
        for suffix in ('.srt','.captions.json','.music.txt','.upload.json'):
            source=final.with_suffix(suffix)
            if source.exists() and not dest.with_suffix(suffix).exists():shutil.copy2(source,dest.with_suffix(suffix))
        state['outputs'].append({'project':str(p),'title':doc.get('editorial',{}).get('premise',p.name),'summary':doc.get('editorial',{}).get('payoff',''),'ranges':[(c['start'],c['start']+c['duration']) for c in doc['clips']],'duration':q['actual_duration'],'qa':q['status'],'music':q.get('music'),'creative_review':str(p/'creative_review.json'),'output':str(dest),'sha256':q['output_sha256']})

def main():
    if __import__('common').config().get('editorial_policy')=='dialogue-editorial-v1':
        from dialogue_mission import continue_mission
        return continue_mission()
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    store=GameStore();r=store.recording()
    state=read(STATE) if STATE.exists() else {'mission_id':key({'source':r['sha256'],'started':now()})[:12],'started_utc':now(),'source_sha256':r['sha256'],'batches':[],'outputs':[],'planning_repairs':0}
    state.setdefault('review_folder',str(ROOT/'ReadyForReview'/('cairn_first_three_'+state['mission_id'])))
    state.pop('error',None)
    state.pop('traceback',None)
    with locked(ROOT/'Database/.full_analysis_mission.lock'):
        try:
            # Recover deliveries after a crash between successful rendering and
            # copying the review file; never create a fourth story to replace it.
            for batch_id in state['batches']:
                prior=store.batch(batch_id)
                if prior['status']=='ready_for_review':deliver(prior,state)
            if len(state['outputs'])>=3:
                write(state,'complete');return
            write(state,'pilot_validation')
            local_index.execute(pilot_only=True)
            state['analysis']=read(EVIDENCE/'progress.json')
            write(state,'local_validation_passed_continuing_full_recording')
            local_index.execute()
            write(state,'index_complete_selecting_unique_stories')
            for attempt in range(5):
                if len(state['outputs'])>=3:break
                unfinished=[store.batch(b) for b in state['batches'] if not any(o['project']==i['project'] for o in state['outputs'] for i in store.batch(b)['items']) and store.batch(b)['status'] not in ('closed','ready_for_review')]
                if unfinished:
                    if len(unfinished)==1 and unfinished[0]['status']=='needs_attention':
                        marker=EVIDENCE/'expanded-policy-resume.json'
                        authorization=read(marker) if marker.exists() else {}
                        batch=unfinished[0]
                        safe=authorization.get('batch')==batch['id'] and authorization.get('status')=='authorized_new_policy' and all(not i['job'] and not (Path(i['project'])/'edit_plan.json').exists() for i in batch['items'])
                        if safe:
                            authorization['status']='started';save(marker,authorization)
                            full_game.main(['batch','--retry',batch['id'],'--start'])
                            unfinished=[store.batch(batch['id'])]
                    if len(unfinished)!=1 or unfinished[0]['status']!='planned':raise RuntimeError('An existing production/voice attempt needs explicit inspection; no blind retry')
                    batch=unfinished[0]
                elif 'pending_creation' in state:
                    new=[b for b in batch_ids(store) if b not in state['pending_creation']]
                    if len(new)!=1:raise RuntimeError('Interrupted batch creation requires explicit inspection; no duplicate planning')
                    batch=store.batch(new[0]);state['batches'].append(batch['id']);state.pop('pending_creation');write(state,'recovered_batch_identity')
                else:
                    state['pending_creation']=batch_ids(store);write(state,'planning_unique_story')
                    try:batch=full_game.main(['batch','--count','1','--start'])
                    except Exception:
                        new=[b for b in batch_ids(store) if b not in state['pending_creation']]
                        if len(new)==1:state['batches'].append(new[0])
                        state.pop('pending_creation',None)
                        # Only a saved, definite editorial rejection permits trying
                        # different evidence. Uncertain AI or speech is never retried.
                        rejected_ids=set()
                        if len(new)==1:
                            failed=store.batch(new[0])
                            for item in failed['items']:
                                project=Path(item['project'])
                                for name in ('rejected_evidence.json','creative_rejection.json'):
                                    if not (project/name).exists():continue
                                    payload=read(project/name)
                                    doc=payload.get('plan') or (read(project/'edit_plan.candidate.json') if (project/'edit_plan.candidate.json').exists() else {})
                                    rejected_ids.update(c['scene_id'] for c in doc.get('clips',[]) if c.get('scene_id'))
                            if rejected_ids and state['planning_repairs']<2:
                                with store.connect() as db:
                                    for scene in rejected_ids:db.execute('UPDATE game_scenes SET rejected=? WHERE id=?',('Bounded automatic exclusion after definite editorial/evidence rejection',scene))
                                store.close_batch(new[0],'Definite editorial rejection; evidence preserved, try a different event')
                                state['planning_repairs']+=1
                                write(state,'rejected_event_trying_distinct_material')
                                continue
                        raise
                    state['batches'].append(batch['id']);state.pop('pending_creation',None);write(state,'story_planned')
                if batch['status']!='planned':raise RuntimeError('Existing batch needs inspection; no automatic analysis or voice retry')
                write(state,'producing_unique_story')
                produced=game_plan.run_batch(batch['id']);deliver(produced,state)
                write(state,'review_files_updated')
                if produced['status']!='ready_for_review':raise RuntimeError('Production job needs attention; saved speech/output preserved, no uncertain TTS retry')
            state['analysis']=read(EVIDENCE/'progress.json')
            inventory=store.inventory()
            state['events']=[{k:s[k] for k in ('id','start','end','description','category','score','eligible')} for s in inventory['scenes']]
            state['eligible_remaining']=inventory['available']
            write(state,'complete' if len(state['outputs'])>=3 else 'complete_fewer_than_three_valid_stories')
        except BaseException as error:
            state['analysis']=read(EVIDENCE/'progress.json') if (EVIDENCE/'progress.json').exists() else None
            state['traceback']=traceback.format_exc()
            write(state,'needs_attention',error)
            raise

if __name__=='__main__':main()
