"""Stop only obsolete pre-speech planning; preserve its unknown outcome and media."""
import sys,os,signal,time,sqlite3,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,state
from game_store import GameStore
import gaming_shorts as gs,editorial
root=gs.ROOT;release=root/'Releases/2026-11-14-dialogue-editorial';release.mkdir(exist_ok=True)
store=GameStore();mission=read(root/'Releases/2026-11-13-full-analysis/mission-state.json')
with store.connect() as db:
    with sqlite3.connect(release/'before.sqlite3') as backup:db.backup(backup)
    active=[dict(x) for x in db.execute("SELECT id FROM game_batches WHERE status IN ('planning','needs_attention')")]
    for b in active:
        if any(i['job'] for i in store.batch(b['id'])['items']):raise RuntimeError('A production job exists: inspect before cancelling')
pid=int(sys.argv[1]);proc=Path(f'/proc/{pid}')
if proc.exists():
    cmd=(proc/'cmdline').read_bytes()
    if b'continue_expanded_mission.py' not in cmd:raise ValueError('Unexpected controller')
    save(release/'obsolete-planning-handoff.json',{'pid':pid,'cancelled_utc':now(),'reason':'User replaced recap policy with dialogue-aware editorial requirements','old_requests_retained':True})
    os.kill(pid,signal.SIGINT)
    for _ in range(60):
        if not proc.exists():break
        time.sleep(1)
    else:raise RuntimeError('Controller did not exit; no replacement may start')
project=root/'Projects/V2/videoplayback_e772d2c8_game_af978f310d6b3fbcb224_1'
feedback='User rejected robot Short editorial quality: redundant recap repeats visible dialogue/emotions, unnecessary cuts and ice-wall filler, generic Subscribe for more ending. Prefer dialogue-aware added-value commentary or gameplay-first continuity and optional CTA. Preserve this rejected output and its footage history.'
editorial.remember(project,'rejected',feedback)
save(project/'editorial_user_rejection.json',{'updated_utc':now(),'feedback':feedback,'output_preserved':True})
state(project,'rejected',reason=feedback)
with zipfile.ZipFile(release/'before-runtime.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for p in (root/'Automation/gamingshorts_v2').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:archive.write(p,p.relative_to(root))
print('Obsolete planning stopped; robot rejection recorded; original and previous output preserved.')
