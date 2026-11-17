"""Invalidate only unrendered reservations made before the mood-fit correction.

The owning batch is still rendering Crystal; these two projects have no active
render artifacts. No music bytes, previous exports or usage history are removed.
"""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key
import gaming_shorts as gs,editorial
release=gs.ROOT/'Releases/2026-11-15-story-reuse'
projects=[Path(read(release/(name+'_plan.json'))['project']) for name in ('marco_choice','rainbow_logic')]
if any((p/'Renders').exists() or (p/'qc_report.json').exists() for p in projects):raise ValueError('A target has started rendering; wait for batch completion instead')
with editorial.connect() as db:
    db.execute('BEGIN IMMEDIATE')
    before=[]
    for p in projects:
        pk=key(read(p/'edit_plan.json'))
        row=db.execute('SELECT selection_key,selection_json FROM music_assignments_v2 WHERE project=? AND plan_key=?',(str(p),pk)).fetchone()
        if not row:raise ValueError('Missing unrendered music reservation')
        before.append({'project':str(p),'selection_key':row[0],'selection':json.loads(row[1])})
    save(release/'music-reservations-before-mood-fix.json',before)
    for p in projects:db.execute("UPDATE music_assignments_v2 SET selection_key='invalidated_after_mood_fit_correction' WHERE project=? AND status='reserved'",(str(p),))
print('Two unrendered music reservations invalidated; next selection uses corrected mood ranking.')
