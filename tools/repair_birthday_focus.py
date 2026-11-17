"""One evidence-directed reframe, capped at four actual drafts for this event."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
from dialogue_mission import release,state_path,continue_mission
import gaming_shorts as gs
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'):
    state=read(state_path());comparison=read(release()/'comparison.json')
    if state.get('birthday_focus_repair'):raise ValueError('Single focus repair already attempted; preserve any hold')
    item=next(c for c in state['candidates'] if c['event_id']=='birthday');p=Path(item['project'])
    if item['status']!='held' or 'face' not in item.get('error',''):raise ValueError('Not the diagnosed framing defect')
    if len(list((p/'Renders').glob('*/candidate.mp4')))>=4:raise ValueError('Four-draft repair budget exhausted')
    archive=p/'EditorialRevisions'/('before_focus_'+key(item)[:12]);archive.mkdir(parents=True,exist_ok=True)
    for name in ('edit_plan.json','dialogue_editorial_review.json','creative_review.json','qc_report.json','portrait_editorial_review.json'):
        path=p/name
        if path.exists() and not (archive/name).exists():shutil.copy2(path,archive/name)
    for choice in comparison['comparison']['candidates']:
        if choice['event_id']=='birthday':choice['focus_x']=.66
    item.update(focus_x=.66,status='not queued',quality='pending',originality='pending',previous_focus_hold=item.pop('error'))
    state['birthday_focus_repair']={'created_utc':now(),'focus_x':.66,'reason':'Original end frame shows recipient and device on right; previous crop showed empty tent and hand','max_actual_drafts':4}
    save(state_path(),state);save(release()/'comparison.json',comparison)
continue_mission()
