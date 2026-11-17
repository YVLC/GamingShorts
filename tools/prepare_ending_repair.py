"""Local-only timing draft; does not approve, reserve, render or request speech."""
import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now
from game_store import GameStore
import gaming_shorts as gs,shared_index
project=gs.ROOT/'Projects/V2/videoplayback_e772d2c8_game_040ca9615cde019a2a2d_1'
rejected=read(project/'rejected_evidence.json')
if not all('final' in issue.lower() or 'cta' in issue.lower() for issue in rejected['review']['issues']):raise ValueError('Not solely an ending-timing rejection')
doc=copy.deepcopy(rejected['plan']);last=doc['clips'][-1]
last['duration']=float(last['duration'])+2.25
scene=next(s for s in GameStore().scenes(GameStore().recording()['id']) if s['id']==last['scene_id'])
assert last['start']>=scene['start'] and last['start']+last['duration']<=scene['end']
assert 2<=last['duration']<=12 and 25<=sum(c['duration'] for c in doc['clips'])<=40
folder=gs.ROOT/'Releases/2026-11-14-ai-resume/ending-repair';folder.mkdir(exist_ok=True)
image=shared_index.dense(project,last['start'],last['duration'])
save(folder/'draft.json',doc)
save(folder/'local-evidence.json',{'original_project':str(project),'original_plan_key':key(rejected['plan']),'repaired_plan_key':key(doc),'updated_utc':now(),'new_ending_preview':str(image),'extra_source_seconds':2.25,'status':'draft_requires_existing_independent_evidence_and_originality_checks; no production authorized by this file'})
print(json.dumps({'draft':str(folder/'draft.json'),'new_ending_preview':str(image),'duration':sum(c['duration'] for c in doc['clips'])},indent=2))
