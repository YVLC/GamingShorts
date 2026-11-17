"""Bounded source/output comparison for the held dialogue render."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,run
from quality_checks import measure_cadence,rate
import gaming_shorts as gs
p=gs.ROOT/'Projects/V2/videoplayback_e772d2c8_dlg_91f9ff2ff828ed63'
source=Path(read(p/'manifest.json')['source']);shot=next((p/'Renders').glob('*/shot_01.mp4'))
fps=rate('19001/317');height=2160*(1080/3840)/1920;roi=(0,(1-height)/2,1,height)
result={'source':measure_cadence(source,10331,3,fps),'output':measure_cadence(shot,0,3,fps,roi=roi),'probe':gs.probe(shot)}
dest=gs.ROOT/'Releases/2026-11-14-dialogue-editorial'
save(dest/'cadence-diagnostic.json',result)
run(['ffmpeg','-v','error','-nostdin','-y','-ss','1','-i',shot,'-frames:v','1','-vf','scale=540:960',dest/'held_portrait.jpg'])
print(json.dumps({k:result[k] for k in ('source','output')},indent=2))
