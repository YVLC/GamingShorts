"""Freeze the two user-approved examples; never infer approval from technical QC."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import HERE,read,save,key,digest,now
import gaming_shorts as gs
rows=[]
for event in ('kami_history','crafted_mountain'):
    delivery=read(gs.ROOT/f'Releases/2026-11-15-visual-stories-v2/{event}_delivery.json')
    meta=read(gs.ROOT/f'Releases/2026-11-15-visual-stories-v2/{event}_plan.json')
    p=Path(meta['project']);plan=read(p/'edit_plan.json');q=read(p/'qc_report.json');approval=read(p/'approval.json')
    if not gs.completed(p) or approval['input_key']!=q['input_key'] or approval['output_sha256']!=q['output_sha256'] or digest(delivery['output'])!=q['output_sha256']:
        raise ValueError('Approval does not identify the exact reviewed bytes')
    rows.append({'id':event,'project':str(p),'output':delivery['output'],'output_sha256':q['output_sha256'],
        'plan_key':key(plan),'approval':approval,'plan':plan})
save(HERE/'approved_quality_reference.json',{'schema':1,'approved_utc':now(),
    'approval_basis':'User explicitly approved these two clips and requested upload and pipeline replication on 2026-11-15.',
    'examples':rows})
prefs=read(HERE/'preferences.json')
prefs['approved']+=['2026-11-15 visual-stories-v2 batch: environmental lore and verified design facts',
    'Full-frame subject tracking, original pixels, CRF 16, native frame cadence',
    'Caption placement avoids important native game labels and controls']
prefs['quality_reference']='approved_quality_reference.json'
prefs['quality_standard']='Use the approved batch as a style and finish reference, never as permission to repeat its hooks, scripts or facts. Pick a clear discovery or useful idea, write natural concrete narration, verify outside facts, inspect the actual crop with a representative caption before speech, and preserve the free Garret voice and full yellow word timing.'
prefs['publication_authorization']={'date':'2026-11-15','approved_output_sha256':[r['output_sha256'] for r in rows],
    'scope':'Upload these two exact approved exports. Future clips still require user approval.'}
save(HERE/'preferences.json',prefs)
print('Captured two byte-bound approved quality examples.')
