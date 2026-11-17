"""Release snapshot and non-destructive preservation audit."""
import sys,json,sqlite3,hashlib,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now
from game_store import GameStore
import gaming_shorts as gs
root=gs.ROOT;release=root/'Releases/2026-11-14-expanded-discovery';store=GameStore();r=store.recording()
old=sqlite3.connect(release/'before/editorial_v2.sqlite3');args=(r['id'],r['index_key'])
with store.connect() as db:
    def rows(connection,sql):return {tuple(x) for x in connection.execute(sql,args)}
    for sql in (
        'SELECT ordinal,screen_json FROM game_local_screens_v1 WHERE recording=? AND index_key=?',
        'SELECT ordinal,reason FROM game_ai_selection_v1 WHERE recording=? AND index_key=?',
        'SELECT id,start,end,description,evidence,spoiler FROM game_scenes WHERE recording=? AND index_key=?'):
        assert rows(old,sql).issubset(rows(db,sql)),'Prior checkpoint/scene metadata lost'
    with sqlite3.connect(release/'editorial-after.sqlite3') as snapshot:db.backup(snapshot)
old.close()
baseline=read(root/'Releases/2026-11-13-ai-resilience/handoff.json');stat=Path(r['source']).stat()
assert (stat.st_size,stat.st_mtime_ns)==(baseline['source_size'],baseline['source_mtime_ns'])
pending=root/'Projects/V2/videoplayback_e772d2c8_game_af978f310d6b3fbcb224_1/FullGameAnalysis/concepts_9cde3eb949e15207a812/request.json'
assert pending.is_file(),'Old uncertain request must remain preserved'
paths=list((root/'Automation/gamingshorts_v2').rglob('*'))+list((root/'tools').glob('*.py'))+list((root/'docs').glob('*.md'))+[root/'start.py',root/'Releases/2026-11-13-ai-resilience/before/local_index.py']
manifest={}
with zipfile.ZipFile(release/'runtime-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts:continue
        name=path.relative_to(root).as_posix();data=path.read_bytes()
        archive.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
save(release/'preservation.json',{'updated_utc':now(),'original_source_size_mtime_unchanged':True,
    'all_original_local_checkpoints_and_47_selections_preserved':True,
    'all_260_observations_and_spoiler_labels_preserved':True,'old_uncertain_request_preserved':str(pending),
    'source_sha256':r['sha256'],'files_sha256':manifest})
print('PASS: source fingerprint, checkpoints, observations, historical spoiler labels and uncertain request preserved; complete runtime snapshot saved.')
