"""Bounded real-source check; no AI, speech, publication or full-source decode."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Automation/gamingshorts_v2'))
from common import configured_source, config, save
from job_store import stat_key
import game_index
import render_sources
import gaming_shorts as gs

folder = Path(config()['root']) / 'Releases/2026-11-12-source-activation/smoke'
folder.mkdir(parents=True, exist_ok=True)
source = configured_source()
before = stat_key(source.stat())
def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=240)
    if result.returncode or result.stderr.strip():
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout
meta = json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
save(folder/'probe.json', meta)
duration = float(meta['format']['duration'])
for i, at in enumerate((60, duration/2, duration-15)):
    run(['ffmpeg','-v','error','-xerror','-threads','2','-ss',str(at),'-i',str(source),'-frames:v','1','-vf','scale=960:-2','-threads','2','-y',str(folder/f'frame_{i}.png')])
r = {'source':str(source), 'fingerprint':before}
artifacts = game_index.make_artifacts(r, folder/'proxy', 60, 68)
proxy_stat = (folder/'proxy/analysis.mp4').stat().st_mtime_ns
assert game_index.make_artifacts(r, folder/'proxy', 60, 68) == artifacts
assert (folder/'proxy/analysis.mp4').stat().st_mtime_ns == proxy_stat
video = next(s for s in meta['streams'] if s['codec_type']=='video')
from quality_checks import rate, production_source
production_source(source)
resolved={'path':source,'start':60,'duration':3,'width':video['width'],'height':video['height'],'fps':rate(video['avg_frame_rate'])}
graph, framing = render_sources.picture_filters(resolved, config(), 'auto')
run(['ffmpeg','-v','error','-xerror','-threads','2','-ss','60','-i',str(source),'-t','3','-an','-vf',graph+',format=yuv420p','-filter_threads','2','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-y',str(folder/'original_render.mp4')])
run(['ffmpeg','-v','error','-xerror','-i',str(folder/'original_render.mp4'),'-f','null','-'])
assert before == stat_key(source.stat()), 'Original metadata changed'
save(folder/'result.json', {'status':'pass','source':str(source),'fingerprint_unchanged':True,'duration':duration,'fps':str(resolved['fps']),'audio_streams':[s for s in meta['streams'] if s['codec_type']=='audio'],'sample_times':[60,duration/2,duration-15],'proxy_reuse':True,'render_framing':framing,'full_decode':False})
print(json.dumps({'status':'pass','folder':str(folder)}))

