import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,config,run
import gaming_shorts as gs,render_sources
p=gs.ROOT/'Projects/V2/videoplayback_e772d2c8_story_reuse_marco_choice'
doc=read(p/'edit_plan.json');source=render_sources.resolve(read(p/'manifest.json'),doc['clips'][1],gs.probe)
graph,_=render_sources.picture_filters(source,config(),'blur_contain')
run(['ffmpeg','-v','error','-y','-ss',16402.8,'-i',source['path'],'-vf',graph,'-frames:v','1',gs.ROOT/'Releases/2026-11-15-story-reuse/marco_wide_preview.png'])
