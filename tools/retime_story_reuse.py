"""Fit saved Crystal narration by moving cuts inside unchanged source coverage."""
import sys,copy,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,locked
import gaming_shorts as gs,game_plan,story_policy,creative_history,editorial,shared_index,voices
from game_store import GameStore
from game_index import cached_ai

release=gs.ROOT/'Releases/2026-11-15-story-reuse'
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    metadata=read(release/'crystal_lore_plan.json');p=Path(metadata['project']);old=read(p/'edit_plan.json');doc=copy.deepcopy(old)
    for c,(a,d) in zip(doc['clips'],[(10322,7),(10329,8),(10337,11)]):c.update(start=a,duration=d)
    if [(c['start'],c['duration']) for c in old['clips']]==[(c['start'],c['duration']) for c in doc['clips']]:print('Already retimed');raise SystemExit(0)
    images=[shared_index.dense(p,c['start'],c['duration']) for c in doc['clips']]
    r=GameStore().recording();scene=next(s for s in GameStore().scenes() if s['id']==doc['clips'][0]['scene_id'])
    game_plan.validate_windows(doc['clips'],[scene],r)
    story_policy.validate(doc)
    review=cached_ai(p/'StoryReuseTiming',story_policy.BRIEF+' Independently check this retimed plan. Exact same original source coverage and narration; cuts shifted to fit saved natural speech. Verify all narration claims remain supported, timing does not imply unseen events, the hook is paid off and CTA follows payoff. immediate_action means compelling hook, not physical motion. No tools. Return schema JSON. Plan: '+json.dumps(doc),game_plan.REVIEW,images,'timed_evidence_review')
    if not story_policy.review_passes(review):raise ValueError('Retimed evidence review failed: '+json.dumps(review))
    archive=p/'TimingRevisions/before_speech_fit';archive.mkdir(parents=True,exist_ok=True)
    for name in ('edit_plan.json','evidence_review.json','creative_review.json'):
        if not (archive/name).exists():shutil.copy2(p/name,archive/name)
    creative_history.require_review(p,doc,invoke=True,images=images)
    GameStore().reserve(p,doc,[scene])
    save(p/'evidence_review.json',{'plan_key':key(doc),'index_key':r['index_key'],'review':review,'story_identity':story_policy.receipt_identity(p,doc),'inspected':[(c['scene_id'],c['start'],c['start']+c['duration']) for c in doc['clips']]})
    save(p/'edit_plan.json',doc);editorial.remember(p)
    metadata.update(plan=doc,speech_request=voices.request(doc['clips']));save(release/'crystal_lore_plan.json',metadata)
    print('Saved source-equivalent retiming; original audio retained',flush=True)
