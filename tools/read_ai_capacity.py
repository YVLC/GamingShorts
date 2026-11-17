"""One read-only Codex capacity check; no model request or state reset."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
import ai_capacity,gaming_shorts as gs
from common import save,now
limits=ai_capacity.capacity_read()
result={'updated_utc':now(),'available':ai_capacity.available(limits),'limits':limits.get('rateLimits')}
save(gs.ROOT/'Releases/2026-11-14-ai-resume/current-capacity.json',result)
print(json.dumps(result,indent=2))
