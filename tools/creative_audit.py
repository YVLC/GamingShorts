"""Build/read the creative ledger and attempt a cache-only batch. Never indexes a source."""
from pathlib import Path
import sys,json,sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import save,key,now,read
import creative_history as creative
from game_store import GameStore
import gaming_shorts as gs

root=gs.ROOT;release=root/'Releases/2026-11-13-creative-diversity';release.mkdir(exist_ok=True)
for name in ('editorial_v2','automation'):
 dest=release/'before'/(name+'.sqlite3')
 if not dest.exists():
  with sqlite3.connect(root/'Database'/(name+'.sqlite3')) as src,sqlite3.connect(dest) as dst:src.backup(dst)
index=creative.refresh();save(release/'historical-index.json',index)
store=GameStore();inventory=store.inventory();r=inventory['recording']
report={'requested':3,'produced':0,'status':'blocked_insufficient_analyzed_footage','active_source':r['source'],'source_sha256':r['sha256'],'indexed_scenes':len(inventory['scenes']),'eligible_scenes':inventory['available'],'completed_analysis_chunks':sum(c['status']=='complete' for c in inventory['chunks']),'pending_chunks':sum(c['status']=='pending' for c in inventory['chunks']),'history_stories':len(index['stories']),'historical_families':index['families'],'original_scan_resumed':False,'reason':'No completed scene analysis for the active authoritative recording. Integrity windows are not narrative analysis. Older recording surveys have different SHA256/timelines and are not silently remapped.','attempts':[{'slot':i,'result':'not_rendered','source_timestamps':None,'narrative':None,'reason':'No eligible analyzed core event; old stories will not be recycled'} for i in range(1,4)]}
# Acceptance attempt uses existing eligibility, not a relaxed guard or a new scan.
if inventory['available']>=9 and r['status']=='indexed':
 report.update(status='candidates_available_requires_normal_review',reason='Run existing controlled batch planning; all independent creative gates now apply.')
with creative.editorial.connect() as db:
 creative.initialize(db);db.execute('INSERT OR IGNORE INTO story_attempts_v1 VALUES (?,?,?,?,?)',(key(report),3,report['status'],json.dumps(report),now()))
save(release/'acceptance.json',report)
# Confirm the known music preview is a remix by independent encoded-frame comparison.
plan=read(root/'Releases/2026-11-13-music-segments/preview_project/edit_plan.json')
preview=Path(read(root/'ReadyForReview/music_segments_2026-11-13/review_report.json')['output'])
visuals=creative.decode_visual_cache(preview,plan,release/'remix-visuals.json')['frames']
proof={'comparison':creative.compare(plan,{},index['stories']),'visual_matches':creative.visual_repetition(visuals,index['stories']),'role':'existing music demo; not a new story'}
save(release/'known-remix-rejection.json',proof)
print(json.dumps(report,indent=2))
