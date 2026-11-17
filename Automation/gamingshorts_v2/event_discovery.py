"""Semantic event families from existing observations; never editorial approval."""
import json
from pathlib import Path
from common import key,read,save,now
import editorial,creative_history,gaming_shorts as gs
from game_store import GameStore
from game_index import cached_ai
import story_policy

EVENT=editorial.obj({'premise':editorial.S,'central_event':editorial.S,'visible_outcome':editorial.S,
    'narrative_angle':editorial.S,'scene_ids':{'type':'array','minItems':1,'maxItems':95,'items':editorial.S},
    'suitable':{'type':'boolean'},'confidence':{'type':'number','minimum':0,'maximum':1},'reason':editorial.S})
SCHEMA=editorial.obj({'events':{'type':'array','maxItems':95,'items':EVENT},
    'rejected':{'type':'array','maxItems':95,'items':editorial.obj({'scene_id':editorial.S,'reason':editorial.S})}})

def folder(r):return gs.ROOT/'FootageIndex'/('sha256_'+r['sha256'])/'CreativeDiscovery_v3'

def eligibility(scene,store):
    reasons=[]
    if scene['confidence']<.75:reasons.append('low_visual_confidence')
    if scene['score']<.5:reasons.append('low_interest_score')
    if scene['rejected']:reasons.append('prior_explicit_hold')
    if scene['category'] in ('map','menu','static','unknown'):reasons.append('non_event_category')
    if scene['end']-scene['start']<4:reasons.append('less_than_four_seconds')
    if not json.loads(scene['hashes_json']):reasons.append('missing_visual_fingerprints')
    if not store.eligible(scene):
        if not reasons:reasons.append('protected_footage_visual_match_or_bridge_exclusion')
    return reasons

def build():
    store=GameStore();r=store.recording();all_scenes=store.scenes(r['id'])
    eligible=[s for s in all_scenes if not eligibility(s,store)]
    from quality_reference import context as quality_context
    reference=quality_context()
    policy=key({'source':r['sha256'],'index_key':r['index_key'],'story_policy':story_policy.VERSION,'quality_reference':reference,
        'observations':[{k:s[k] for k in ('id','description','evidence','start','end','rejected','score')} for s in all_scenes]})
    path=folder(r)/'catalog.json'
    if path.exists() and read(path).get('policy_key')==policy:return read(path)
    history=[{'id':h['id'],'facts':h['facts']} for h in creative_history.history()]
    aliases={f's{i:03}':s['id'] for i,s in enumerate(eligible)}
    summaries=[dict({k:s[k] for k in ('start','end','description','evidence','category','score')},id=alias) for alias,s in zip(aliases,eligible)]
    prompt=('Group the supplied eligible Cairn observations into DISTINCT CONCRETE EVENT/STORY FAMILIES. '
        'Different observations, timestamps, locations or rewritten wording are not automatically different stories. '
        'Group repeated instances of the same core mechanic/event and equivalent payoff together. '
        'Keep genuinely different central events separate. Account for EVERY scene_id exactly once, either in one event or rejected. '
        'Base claims only on the supplied descriptions/evidence; this is preliminary semantic discovery, NOT visual approval. '
        'A suitable family needs a concrete visible event and supported outcome, enough coherent footage for a 25-40 second Short, '
        'an original hook/angle compared to history, and no unrelated filler, invented lore or forced cliffhanger. '
        'Generic climbing, more coffee instead of hot chocolate, and the same rainbow transition already covered are not new stories. '
        'Prefer failures, recoveries, strange encounters, discoveries, surprising mechanics, humor and visually clear outcomes. '
        + story_policy.BRIEF + ' Approved style/finish reference (not factual evidence): '+json.dumps(reference)+
        'Return schema JSON only. No tools or commands. Historical stories: '+json.dumps(history)+
        ' Observations: '+json.dumps(summaries))
    result=cached_ai(folder(r),prompt,SCHEMA,[],'semantic_event_families')
    for event in result['events']:event['scene_ids']=[aliases[i] for i in event['scene_ids']]
    # A rejection of a nonexistent identifier cannot represent real footage or
    # inflate rejection counts. Keep it as a model warning; real IDs must still
    # be fully and uniquely accounted for below. Unknown event members fail.
    warnings=[x for x in result['rejected'] if x['scene_id'] not in aliases]
    result['rejected']=[dict(x,scene_id=aliases[x['scene_id']]) for x in result['rejected'] if x['scene_id'] in aliases]
    valid={s['id']:s for s in eligible};seen=[];events=[]
    for event in result['events']:
        ids=event['scene_ids']
        if not ids or any(i not in valid for i in ids):raise ValueError('Event family references unknown scene')
        seen+=ids
        events.append(dict(event,id=key({'policy':policy,'scenes':sorted(ids)})[:24],
            source_ranges=[(valid[i]['start'],valid[i]['end']) for i in ids],
            independent_creative_review='pending',rendering='not_queued',technical_qc='not_run',preview=None))
    seen += [s['scene_id'] for s in result['rejected']]
    if len(seen)!=len(set(seen)) or set(seen)!=set(valid):raise ValueError('Semantic grouping must account for each eligible observation exactly once')
    report={'policy_key':policy,'selection_policy':'visual-stories-v2-approved','updated_utc':now(),'recording':r['id'],'index_key':r['index_key'],
        'observations':len(all_scenes),'technical_candidates':len(eligible),'events':events,'rejected':result['rejected'],'model_warnings':warnings,
        'observation_rejections':[{'scene_id':s['id'],'reasons':eligibility(s,store)} for s in all_scenes if eligibility(s,store)],
        'limitation':'Semantic event families are provisional. Independent visual/evidence and creative-history reviews remain mandatory.'}
    save(path,report);return report

def visual_priority(scene):
    """Retrieval hints only; source and originality review still decide suitability."""
    import re
    text=' '.join(str(scene.get(k,'')) for k in ('description','evidence')).lower()
    conversation=bool(re.search(r'\b(dialogue|conversation|talking|speaks|subtitles|marco)\b',text))
    world=bool(re.search(r'\b(ruins|artifact|architecture|cavern|secret|piton|panorama|sunset|rainbow)\b',text))
    return (conversation,-int(world),-float(scene.get('score',0)))

def prioritized(scenes,r):
    path=folder(r)/'catalog.json'
    if not path.exists():return sorted(scenes,key=visual_priority)
    catalog=read(path)
    if catalog['index_key']!=r['index_key']:return sorted(scenes,key=visual_priority)
    store=GameStore()
    by_id={s['id']:s for s in scenes if s['end']-s['start']>=4 and store.eligible(s)};ordered=[];used=set()
    # Old conversation-oriented grouping is not a selection mandate. Reuse the
    # existing observations while a new semantic catalog is built; no rescan.
    if catalog.get('selection_policy')!='visual-stories-v2-approved':return sorted(by_id.values(),key=visual_priority)
    # Ranking hints only: physical actions are more likely to support the
    # unchanged immediate-action and visible-outcome checks than seated dialogue.
    weights={k:5 for k in story_policy.ANGLES};weights.update(failure=4,action=4,mechanic=5,discovery=5,unusual=4,climb=1)
    def action_rank(event):
        return max((weights.get(by_id[i].get('category','unknown'),0) for i in event['scene_ids'] if i in by_id),default=0)
    groups=sorted(catalog['events'],key=lambda e:(not e['suitable'],-action_rank(e),-e['confidence'],e['id']))
    groups=[e for e in groups if e['suitable'] and e['confidence']>=.8]
    with GameStore().connect() as db:
        reserved={x[0] for x in db.execute('SELECT scene FROM game_shots')}
    groups=[e for e in groups if (story_policy.reuse_allowed(r['sha256']) or not reserved.intersection(e['scene_ids'])) and any(i in by_id for i in e['scene_ids'])]
    # Round-robin across semantic families avoids twelve views of one routine.
    for pool in (groups[:3],groups[3:]):
        for n in range(max((len(e['scene_ids']) for e in pool),default=0)):
            for event in pool:
                members=sorted((by_id[i] for i in event['scene_ids'] if i in by_id),key=lambda s:(visual_priority(s),-(s['end']-s['start'])))
                if n<len(members) and members[n]['id'] not in used:
                    ordered.append(members[n]);used.add(members[n]['id'])
    return ordered
