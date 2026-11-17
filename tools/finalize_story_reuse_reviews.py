"""Refresh exact saved commentary reviews after all new outputs enter history."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,locked
import gaming_shorts as gs,creative_history,shared_index,game_plan
release=gs.ROOT/'Releases/2026-11-15-story-reuse'
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    deliveries=list(release.glob('*_delivery.json'))
    if len(deliveries)!=3:raise ValueError('Wait until all three renders finish')
    creative_history.refresh();results=[]
    for path in sorted(deliveries):
        event=path.name.removesuffix('_delivery.json');metadata=read(release/(event+'_plan.json'));p=Path(metadata['project']);doc=read(p/'edit_plan.json')
        images=[shared_index.dense(p,c['start'],c['duration']) for c in doc['clips']]
        review=creative_history.require_review(p,doc,invoke=True,images=images)
        game_plan.guard(p,doc)
        results.append({'event':event,'creative_review_key':review['key'],'status':'passed'})
        print(event+' current saved commentary review passed',flush=True)
    save(release/'current-editorial-reviews.json',results)
