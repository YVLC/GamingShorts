"""Read-only live review report for the resumed mission (no generation)."""
import sys,json,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now
from game_store import GameStore
import gaming_shorts as gs
root=gs.ROOT;release=root/'Releases/2026-11-14-ai-resume'
store=GameStore();inventory=store.inventory();r=inventory['recording']
with store.connect() as db:
    selected=[dict(row) for row in db.execute('SELECT c.ordinal,c.start,c.end,c.status FROM game_ai_selection_v1 s JOIN game_chunks c USING(recording,index_key,ordinal) WHERE s.recording=? AND s.index_key=? ORDER BY c.ordinal',(r['id'],r['index_key']))]
eligible=[s for s in inventory['scenes'] if s['eligible']]
rejected=[s for s in inventory['scenes'] if s['rejected']]
history_blocks=[s for s in inventory['scenes'] if not s['eligible'] and not s['rejected'] and s['spoiler']=='none' and s['confidence']>=.75 and s['score']>=.5 and s['category'] not in ('map','menu','static','unknown')]
state=read(root/'Releases/2026-11-13-full-analysis/mission-state.json')
candidate_rejections=[]
for identity in state.get('batches',[]):
    for item in store.batch(identity)['items']:
        project=Path(item['project'])
        for name,kind in (('creative_rejection.json','creative_repetition'),('rejected_evidence.json','unsupported_evidence')):
            if (project/name).exists():candidate_rejections.append({'project':str(project),'kind':kind,'evidence':read(project/name)})
result={'updated_utc':now(),'stage':state['stage'],'selected_ai_chunks':len(selected),'ai_completed':sum(s['status']=='complete' for s in selected),'remaining_ai_inspections':sum(s['status']!='complete' for s in selected),'scene_observations':len(inventory['scenes']),'eligible_scenes':len(eligible),'eligible_categories':dict(collections.Counter(s['category'] for s in eligible)),'explicit_rejected_scenes':len(rejected),'other_history_visual_or_bridge_blocks':len(history_blocks),'eligible_events':[{k:s[k] for k in ('id','start','end','category','description','score')} for s in eligible],'rejections':[{k:s[k] for k in ('id','start','end','description','rejected')} for s in rejected],'outputs':state.get('outputs',[]),'error':state.get('error'),'publication':'not performed'}
save(release/'review-status.json',result)
result['candidate_rejections']=candidate_rejections
result['quality_reports']=[{'project':out['project'],'report':read(Path(out['project'])/'qc_report.json'),'originality':read(Path(out['project'])/'creative_review.json')} for out in result['outputs']]
save(release/'review-status.json',result)
dest=Path(state['review_folder']);dest.mkdir(exist_ok=True,parents=True)
lines=['# Resumed AI analysis and review','','Updated: '+now(),'Stage: '+state['stage'],f"AI inspections: {result['ai_completed']}/{len(selected)}; remaining: {result['remaining_ai_inspections']}",f"Scene observations: {result['scene_observations']}; eligible scenes: {len(eligible)}",f"Explicit rejected scenes: {len(rejected)}",f"Other history, visual or bridge exclusions: {len(history_blocks)} (not all are story duplicates).",'','Sampling coverage: '+str(release/'coverage.json'),'','Publication: not performed. Technical QA is separate from human approval.','']
lines += [f"Rejected creative candidates: {sum(x['kind']=='creative_repetition' for x in candidate_rejections)}",f"Rejected unsupported candidates: {sum(x['kind']=='unsupported_evidence' for x in candidate_rejections)}",'']
for out in result['outputs']:
    lines+=['## '+out['title'],'','Narrative: '+out['summary'],'Ranges: '+json.dumps(out['ranges']),'Duration: '+str(out['duration']),'Spoiler: '+out['spoiler'],'QA: '+out['qa'],'File: '+out['output'],'']
if result.get('error'):lines+=['Attention: '+result['error']]
(dest/'AI_RESUME_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('eligible_events','rejections','outputs','error','candidate_rejections','quality_reports')},indent=2),flush=True)
