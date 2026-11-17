"""One bounded repair of measured subtitle crop/dwell defects, not review bypass."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
from dialogue_mission import release,state_path,continue_mission
from game_store import GameStore
import gaming_shorts as gs
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'):
    state=read(state_path());comparison=read(release()/'comparison.json');store=GameStore()
    if state.get('readability_revision_started'):raise ValueError('Readability revision already started; resume saved checkpoints')
    scenes={s['id']:s for s in store.scenes(store.recording()['id'])}
    for item in state['candidates']:
        if item['event_id'] not in ('crystal','birthday') or item['status']!='held':continue
        p=Path(item['project']);extra=.5 if item['event_id']=='crystal' else 1.5;duration=item['duration']+extra
        if item['start']+duration>scenes[item['scene_id']]['end']:raise ValueError('Readability tail exceeds indexed evidence: '+str([(x['event_id'],scenes[x['scene_id']]['start'],scenes[x['scene_id']]['end']) for x in state['candidates']]))
        archive=p/'EditorialRevisions'/('before_readability_'+key(item)[:12]);archive.mkdir(parents=True,exist_ok=True)
        for name in ('edit_plan.json','dialogue_editorial_review.json','creative_review.json','creative_rejection.json','qc_report.json','portrait_editorial_review.json'):
            path=p/name
            if path.exists() and not (archive/name).exists():shutil.copy2(path,archive/name)
        reason=item['duration_reason']+f' A {extra}-second continuous source tail permits the final verified line to remain readable; no new dialogue or outcome is claimed.'
        for choice in comparison['comparison']['candidates']:
            if choice['event_id']==item['event_id']:choice.update(duration=duration,duration_reason=reason)
        item.update(duration=duration,duration_reason=reason,status='not queued',quality='pending',originality='pending',previous_readability_hold=item.get('error'))
        item.pop('error',None)
    state['readability_revision_started']=now();save(state_path(),state);save(release()/'comparison.json',comparison)
continue_mission()
