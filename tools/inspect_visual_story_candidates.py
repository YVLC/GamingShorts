import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from game_store import GameStore
s=GameStore();rows=[]
for x in s.scenes():
    text=(x['description']+' '+x['evidence']).lower()
    if x['rejected'] or any(w in text for w in ('marco','subtitles','conversation','birthday','robot','bridge')):continue
    if any(w in text for w in ('temple','statue','ruin','sigil','diagram','cave','wall','waterfall','sunset','snow','rest','piton','chalk','rope','rainbow','night','storm','sunrise','fall','plant','cooking','shelter')):
        rows.append({k:x[k] for k in ('id','start','end','description','evidence','category','score','confidence')})
print(json.dumps(rows,indent=2))
