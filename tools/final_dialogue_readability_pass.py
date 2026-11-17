"""Final bounded repair: exact cut evidence, no unverified source tail."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
from dialogue_mission import release,state_path,continue_mission
import gaming_shorts as gs
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'):
    state=read(state_path());comparison=read(release()/'comparison.json')
    if state.get('final_readability_pass'):raise ValueError('Final bounded pass already started; do not reset failed reviews')
    for item in state['candidates']:
        if item['event_id'] not in ('crystal','birthday') or item['status']!='held':continue
        p=Path(item['project']);archive=p/'EditorialRevisions'/('before_final_readability_'+key(item)[:12]);archive.mkdir(parents=True,exist_ok=True)
        for name in ('edit_plan.json','dialogue_editorial_review.json','creative_review.json','creative_rejection.json','qc_report.json','portrait_editorial_review.json','dialogue_quality_rejection.json'):
            path=p/name
            if path.exists() and not (archive/name).exists():shutil.copy2(path,archive/name)
        duration=16.5 if item['event_id']=='crystal' else 13
        reason=f'{duration} contiguous source seconds complete the dialogue setup and payoff. A clearly declared 1.5-second final-frame reading hold preserves the ending without introducing the next source sentence; no invented action or speech.'
        for choice in comparison['comparison']['candidates']:
            if choice['event_id']==item['event_id']:choice.update(duration=duration,end_reading_hold=1.5,duration_reason=reason)
        item.update(duration=duration,end_reading_hold=1.5,duration_reason=reason,status='not queued',quality='pending',originality='pending',previous_final_hold=item.get('error'))
        item.pop('error',None)
    state['final_readability_pass']=now();save(state_path(),state);save(release()/'comparison.json',comparison)
continue_mission()
