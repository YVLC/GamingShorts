"""Positive editorial examples with explicit user approval and exact output bytes."""
from pathlib import Path
from common import HERE,read,digest,key

def examples(path=None):
    p=Path(path) if path else HERE/'approved_quality_reference.json'
    if not p.exists():return []
    doc=read(p)
    if doc.get('schema')!=1 or not doc.get('approval_basis'):raise ValueError('Invalid approved quality reference')
    result=[]
    for row in doc['examples']:
        approval=row['approval']
        if approval.get('output_sha256')!=row['output_sha256'] or not approval.get('approved_utc') or not approval.get('input_key'):
            raise ValueError('Quality example needs explicit byte-bound approval')
        if key(row['plan'])!=row['plan_key'] or digest(row['output'])!=row['output_sha256']:
            raise ValueError('Approved quality example changed')
        result.append(row)
    return result

def context():
    return {'usage':'Style and finish references only. Do not repeat scripts, hooks, source sequences or assume their facts apply to another story. Every new story needs its own evidence and independent review.',
        'standards':['One concrete interesting idea, a specific hook and an evidenced payoff.',
            'Natural narration that adds context; no production caveats, subtitle retelling or relationship analysis.',
            'Environmental lore, real mechanics, discoveries, humor, scary moments, scenery and verified facts.',
            'Full-frame original footage, conservative subject tracking, no blurred filler.',
            'Check beginning/middle/end crops and caption clearance from native labels/buttons before narration.',
            'Free Garret, real-timestamp yellow words throughout narration, fitting cleared music, final Subscribe for more.'],
        'approved_examples':[{'id':r['id'],'output_sha256':r['output_sha256'],'editorial':r['plan']['editorial'],
            'narration':[c['narration'] for c in r['plan']['clips']]} for r in examples()]}

def approved_current(project,plan):
    """Grandfather only the exact reviewed plans and bytes, not future derivatives."""
    return any(Path(r['project'])==Path(project) and r['plan_key']==key(plan) for r in examples())
