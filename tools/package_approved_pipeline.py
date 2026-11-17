"""Versioned approved-reference release and upload handoff; no publication side effects."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import HERE,save,read,digest,now
import gaming_shorts as gs,quality_reference
release=gs.ROOT/'Releases/2026-11-15-approved-pipeline';release.mkdir(exist_ok=True)
uploads=[]
for row in quality_reference.examples():
    p=Path(row['project']);q=read(p/'qc_report.json');approval=read(p/'approval.json')
    if not gs.completed(p) or approval['output_sha256']!=row['output_sha256'] or approval['input_key']!=q['input_key']:
        raise ValueError('Approved export was invalidated by pipeline changes')
    meta=read(Path(row['output']).with_suffix('.upload.json'))
    uploads.append({'event':row['id'],'file':row['output'],'output_sha256':row['output_sha256'],
        'title':meta['title'],'description':meta['description'],'approval':approval,
        'media_url':None,'status':'awaiting_direct_download_url'})
save(release/'upload_manifest.json',{'updated_utc':now(),'brand_id':'7973666',
    'youtube_channel_id':'UCxhOaZLrqptxHTDGoLKzbrA','timezone':'Europe/Amsterdam',
    'publication_status':'not_uploaded','authorization':'User approved these exact clips and requested upload on 2026-11-15.',
    'blocker':'Connected Metricool publishing requires direct media download URLs. Its exposed tools cannot upload files from the local D: drive.',
    'posts':uploads})
dest=release/'source';dest.mkdir(exist_ok=True)
for f in HERE.iterdir():
    if f.is_file() and f.suffix in ('.py','.json','.md'):shutil.copy2(f,dest/f.name)
shutil.copytree(HERE/'tests',dest/'tests',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
(dest/'tools').mkdir(exist_ok=True)
for name in ('capture_approved_quality.py','package_approved_pipeline.py'):
    shutil.copy2(gs.ROOT/'tools'/name,dest/'tools'/name)
save(release/'source_manifest.json',{str(f.relative_to(dest)):digest(f) for f in dest.rglob('*') if f.is_file()})
print('Exact approved exports remain valid; source snapshot and upload handoff saved.')
