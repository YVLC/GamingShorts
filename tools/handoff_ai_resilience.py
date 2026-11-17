"""One-time graceful live-worker handoff; waits for next checkpoint, no deletion."""
import json,os,signal,sqlite3,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
release=ROOT/'Releases/2026-11-13-ai-resilience'
progress=ROOT/'Releases/2026-11-13-full-analysis/progress.json'
start=json.loads(progress.read_text())['locally_screened']
pid=int(sys.argv[1]) if len(sys.argv)>1 else 47715
print('Waiting for checkpoint after',start,flush=True)
while json.loads(progress.read_text())['locally_screened']<=start:time.sleep(5)
# Capture a consistent database backup before the restart.
with sqlite3.connect(ROOT/'Database/editorial_v2.sqlite3') as source:
    backup=release/'before/editorial_v2.sqlite3' if pid==47715 else release/f'before-handoff-{pid}.sqlite3'
    with sqlite3.connect(backup) as dest:source.backup(dest)
checkpoint=json.loads(progress.read_text())
stat=(ROOT/'Sources/videoplayback.webm').stat()
receipt=release/('handoff.json' if pid==47715 else 'handoff-latest.json')
receipt.write_text(json.dumps({'checkpoint':checkpoint,'source_size':stat.st_size,'source_mtime_ns':stat.st_mtime_ns,'stopped_pid':pid},indent=2))
os.kill(pid,signal.SIGINT)
for i in range(60):
    if not Path(f'/proc/{pid}').exists():break
    time.sleep(1)
else:raise RuntimeError('Worker did not exit gracefully; no second worker started')
print('Graceful handoff complete',checkpoint['locally_screened'],flush=True)
