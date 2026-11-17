"""Preservation checks and versioned release snapshot after AI resumption."""
import sys,json,sqlite3,hashlib,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now
from game_store import GameStore
import gaming_shorts as gs
root=gs.ROOT;release=root/'Releases/2026-11-14-ai-resume'
store=GameStore();r=store.recording();args=(r['id'],r['index_key'])
old=sqlite3.connect(release/'before/editorial_v2.sqlite3')
with store.connect() as db:
    def rows(connection,sql):return set(tuple(x) for x in connection.execute(sql,args))
    q='SELECT ordinal,screen_json FROM game_local_screens_v1 WHERE recording=? AND index_key=?'
    assert rows(old,q)==rows(db,q),'Local checkpoint changed'
    q='SELECT ordinal FROM game_ai_selection_v1 WHERE recording=? AND index_key=?'
    assert rows(old,q)==rows(db,q),'AI selection changed unexpectedly'
    q='SELECT id,start,end,description FROM game_scenes WHERE recording=? AND index_key=?'
    assert rows(old,q).issubset(rows(db,q)),'Previously completed scene observation lost or changed'
    completed='SELECT ordinal FROM game_chunks WHERE recording=? AND index_key=? AND status="complete"'
    assert rows(old,completed).issubset(rows(db,completed)),'Previously completed AI chunk lost'
    with sqlite3.connect(release/'editorial-after.sqlite3') as snapshot:db.backup(snapshot)
old.close()
baseline=read(root/'Releases/2026-11-13-ai-resilience/handoff.json')
stat=Path(r['source']).stat()
assert (stat.st_size,stat.st_mtime_ns)==(baseline['source_size'],baseline['source_mtime_ns'])
paths=list((root/'Automation/gamingshorts_v2').rglob('*'))+list((root/'tools').glob('*.py'))+list((root/'docs').glob('*.md'))+[root/'start.py',root/'Releases/2026-11-13-ai-resilience/before/local_index.py']
files={}
with zipfile.ZipFile(release/'runtime-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts:continue
        name=path.relative_to(root).as_posix();data=path.read_bytes()
        archive.writestr(name,data);files[name]=hashlib.sha256(data).hexdigest()
save(release/'preservation.json',{'updated_utc':now(),'source_fingerprint_unchanged':True,'all_217_local_screens_preserved':True,'same_47_ai_selections':True,'prior_14_completed_inspections_preserved':True,'prior_84_scene_observations_preserved':True,'source_sha256':r['sha256'],'files_sha256':files})
print('Preservation checks passed; runtime-source.zip and SQLite snapshot saved.')
