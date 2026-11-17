import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from game_store import GameStore
s=GameStore();r=s.recording()
print(json.dumps({'recording':{k:r[k] for k in ('id','status','index_key','sha256')},'scenes':[{k:x[k] for k in ('id','start','end','description','category','evidence','score','rejected')} for x in s.scenes() if any(t in (x['description']+' '+x['evidence']).lower() for t in ('rainbow','marco','birthday','crystal','secret','lore','letter','message','memory'))]},indent=2))
with s.connect() as db:print('BATCHES',json.dumps([dict(x) for x in db.execute('SELECT id,status,error FROM game_batches')]))
