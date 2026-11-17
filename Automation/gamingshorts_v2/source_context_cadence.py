"""Explicit source-native cadence admission for written lore and ambient views.

This never repairs/interpolates footage and never admits low-cadence action tips.
The renderer still compares every export against the measured original source.
"""
from pathlib import Path
from common import read,key,digest,save
import story_policy

def accepted(project,plan,clip,recording,result):
    p=Path(project);path=p/'source_context_cadence.json'
    ed=plan.get('editorial',{})
    if ed.get('policy')!='gaming-stories-v2' or ed.get('story_type')!='lore' or ed.get('story_basis')!='world_lore' or not path.exists():return False
    note=read(path)
    if note.get('purpose')!='written_lore_with_ambient_context' or note.get('plan_key')!=key(plan) or note.get('source_sha256')!=recording['sha256']:return False
    review=read(p/'evidence_review.json')
    if review.get('plan_key')!=key(plan) or not story_policy.review_passes(review.get('review',{})):return False
    if not note.get('detail_images') or any(not Path(f).is_file() or digest(f)!=sha for f,sha in note['detail_images'].items()):return False
    for entry in note.get('entries',[]):
        if entry.get('start')==clip['start'] and entry.get('duration')==clip['duration'] and entry.get('result_key')==key(result) and float(result.get('active_updates_per_second') or 0)>=12:
            save(p/'source_cadence_notes.json',note)
            return True
    return False

def record_context(project,plan,recording,details):
    """Record measured original profiles for an explicitly curated lore insert."""
    import json
    import gaming_shorts as gs
    from common import HERE
    from quality_checks import measure_cadence,rate
    p=Path(project);review=read(p/'evidence_review.json')
    if plan['editorial'].get('story_type')!='lore' or plan['editorial'].get('story_basis')!='world_lore' or not story_policy.review_passes(review.get('review',{})) or review.get('plan_key')!=key(plan):raise ValueError('Native lore context requires a current independent source review')
    video=next(s for s in json.loads(recording['probe_json'])['streams'] if s['codec_type']=='video');fps=rate(video['avg_frame_rate']);entries=[]
    for c in plan['clips']:
        seconds=min(3,float(c['duration']));token=key({'source':recording['sha256'],'start':c['start'],'duration':seconds,'fps':str(fps),'qc':digest(HERE/'quality_checks.py')})
        receipt=gs.ROOT/'FootageIndex'/('sha256_'+recording['sha256'])/'ProductionCadence'/(token+'.json')
        result=read(receipt)['result'] if receipt.exists() else measure_cadence(recording['source'],c['start'],seconds,fps)
        if not receipt.exists():save(receipt,{'key':token,'result_key':key(result),'result':result})
        entries.append({'start':c['start'],'duration':c['duration'],'result_key':key(result),'measured_profile':result})
    save(p/'source_context_cadence.json',{'purpose':'written_lore_with_ambient_context','source_sha256':recording['sha256'],'plan_key':key(plan),
        'detail_images':{d['path']:d['sha256'] for d in details},'entries':entries,
        'scope':'Preserve the original written-lore/ambient animation cadence. No interpolation and no claim of smooth 60-fps action. Output-to-source cadence checks remain mandatory.'})
