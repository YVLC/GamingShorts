"""Plain manual-upload metadata with exact rendered music attribution."""
from pathlib import Path
from common import read,save

def music_metadata(project,context=None):
    p=Path(project);context=context or {}
    plan=read(p/'edit_plan.json') if (p/'edit_plan.json').exists() else {}
    ed=plan.get('editorial',{});game=ed.get('game_title') or context.get('game') or 'Gaming'
    meta={'title':f"{game} — {ed.get('premise') or 'Gameplay story'}"[:100],
          'description':f"{ed.get('premise') or 'A gaming story.'}\n\nSubscribe for more.\n\n#GamingShorts",
          'label':''}
    q=read(p/'qc_report.json') if (p/'qc_report.json').exists() else {}
    music=q.get('music',{});credit=music.get('attribution','').strip()
    if music.get('path') and credit:meta['description']+='\n\n'+credit
    return meta

def write_metadata(project):
    p=Path(project);q=read(p/'qc_report.json');meta=music_metadata(p)
    save(Path(q['output']).with_suffix('.upload.json'),dict(meta,output_sha256=q['output_sha256']))
    return meta
