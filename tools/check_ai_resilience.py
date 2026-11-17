"""Read-only capacity + checkpoint identity diagnostic; no model generation."""
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
import ai_capacity,local_index,game_index as index,gaming_shorts as gs
from common import key,digest,config,save
from game_store import GameStore
r=GameStore().recording()
token=key({'source':r['sha256'],'policy':local_index.POLICY,'proxy_policy':index.policy(),'schema':index.SCHEMA,'controller':local_index.SAMPLING_CONTROLLER_SHA256,'validator':index.validator_key('ffmpeg'),'font':digest(config()['font']),'adapter':digest(index.editorial.__file__)})
assert token==r['index_key'], (token,r['index_key'])
try:
    limits=ai_capacity.capacity_read()
    capacity={'read_only_probe':'passed','capacity_available':ai_capacity.available(limits),
              'limits':limits.get('rateLimits')}
    if not capacity['capacity_available']:
        ai_capacity.reject('Read-only capacity check has not confirmed availability',observed=limits)
except Exception as error:
    capacity={'read_only_probe':'unavailable','error_type':type(error).__name__}
with GameStore().connect() as db:
    counts=dict(db.execute('SELECT status,count(*) FROM game_chunks WHERE recording=? AND index_key=? GROUP BY status',(r['id'],token)))
result={'preserved_index_key':token,'chunks':counts,**capacity}
save(gs.ROOT/'Releases/2026-11-13-ai-resilience/verification.json',result)
print(json.dumps(result,indent=2))
