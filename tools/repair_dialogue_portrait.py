"""One new portrait-layout revision; keep all prior plans, proofs and media."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
from dialogue_mission import release,state_path,continue_mission
import gaming_shorts as gs
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'):
    state=read(state_path());comparison=read(release()/'comparison.json')
    if state.get('portrait_revision_started'):raise ValueError('Portrait revision already authorized; resume the saved revision rather than resetting it')
    for item in state['candidates']:
        if item['event_id'] not in ('crystal','birthday') or item['status']!='held':continue
        p=Path(item['project'])
        if (p/'active_voice.json').exists():raise ValueError('Unexpected voice assets; do not retry speech')
        archive=p/'EditorialRevisions'/('before_portrait_'+key(item)[:12]);archive.mkdir(parents=True,exist_ok=True)
        for name in ('edit_plan.json','dialogue_editorial_review.json','creative_review.json','creative_rejection.json','qc_report.json','portrait_editorial_review.json'):
            path=p/name
            if path.exists() and not (archive/name).exists():shutil.copy2(path,archive/name)
        for choice in comparison['comparison']['candidates']:
            if choice['event_id']==item['event_id']:choice.update(framing='dialogue_portrait',focus_x=.43)
        item.update(framing='dialogue_portrait',focus_x=.43,status='not queued',quality='pending',originality='pending',previous_portrait_hold=item.get('error'))
        item.pop('error',None)
        # Existing accepted plans are kept in EditorialRevisions. This separate
        # marker requires fresh plan-bound reviews before a new render.
        save(p/'portrait_revision_request.json',{'source_plan':str(archive/'edit_plan.json'),'created_utc':now(),'framing':'dialogue_portrait'})
    state['portrait_revision_started']=now();save(state_path(),state);save(release()/'comparison.json',comparison)
continue_mission()
