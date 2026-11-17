"""Capture release evidence without touching original media or active workers."""
import hashlib,json,sqlite3,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
release=ROOT/'Releases/2026-11-13-ai-resilience'
handoff=json.loads((release/'handoff.json').read_text())
source=ROOT/'Sources/videoplayback.webm';stat=source.stat()
assert stat.st_size==handoff['source_size'] and stat.st_mtime_ns==handoff['source_mtime_ns']
with sqlite3.connect(ROOT/'Database/editorial_v2.sqlite3') as db:
    with sqlite3.connect(release/'editorial-after.sqlite3') as backup:db.backup(backup)
    old=sqlite3.connect(release/'before/editorial_v2.sqlite3')
    query='SELECT recording,index_key,ordinal,screen_json FROM game_local_screens_v1 WHERE index_key=? ORDER BY ordinal'
    token=handoff['checkpoint']['index_key']
    before=list(old.execute(query,(token,)));after=list(db.execute(query,(token,)))
    assert all(row in after for row in before),'Lost/changed local checkpoint'
    old.close()
processes=[]
for path in Path('/proc').iterdir():
    if not path.name.isdigit():continue
    try:
        args=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        if 'python3' in args and ('tools/resume_full_workflow.py' in args or 'tools/full_analysis_report.py' in args):
            processes.append({'pid':int(path.name),'command':args})
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
paths=list((ROOT/'Automation/gamingshorts_v2').rglob('*'))
paths += list((ROOT/'docs').glob('*.md'))
paths += [ROOT/'start.py']+list((ROOT/'tools').glob('*.py'))
paths += [release/'before/local_index.py'] # Sampling-compatibility regression fixture.
manifest={}
with zipfile.ZipFile(release/'runtime-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts:continue
        relative=path.relative_to(ROOT).as_posix();data=path.read_bytes()
        manifest[relative]=hashlib.sha256(data).hexdigest();archive.writestr(relative,data)
result={'source_fingerprint_unchanged':True,'preserved_local_checkpoints':len(before),
        'current_local_checkpoints':len(after),'index_key':token,'processes':processes,
        'files_sha256':manifest}
(release/'manifest.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='files_sha256'},indent=2))
