import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from game_store import GameStore
s=GameStore()
if len(sys.argv)>2:
    a,b=map(float,sys.argv[1:3])
    print(json.dumps([{k:x[k] for k in ('id','start','end','description','evidence','category','score','confidence','rejected')} for x in s.scenes() if x['end']>a and x['start']<b],indent=2));raise SystemExit
with s.connect() as db:
    batches=[dict(r) for r in db.execute("SELECT id,status,error,created FROM game_batches ORDER BY created DESC")]
    for b in batches:b['items']=[dict(r) for r in db.execute('SELECT project,job FROM game_batch_items WHERE batch=?',(b['id'],))]
print(json.dumps({'batches':batches,'scenes':[{k:x[k] for k in ('id','start','end','description','evidence','category','score','rejected')} for x in s.scenes() if x['category'] in ('mechanic','action','failure','discovery','unusual') and not x['rejected']]},indent=2))
