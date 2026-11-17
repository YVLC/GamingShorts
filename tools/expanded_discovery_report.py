"""Live per-candidate report. Read-only database access; never requests AI."""
import sys,json,time,collections,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,digest,config,key
from game_store import GameStore
import gaming_shorts as gs,event_discovery,creative_history

def hms(n):return f'{int(n//3600):02}:{int(n%3600//60):02}:{n%60:06.3f}'
def ranges(clips):return [(c['start'],c['start']+c['duration']) for c in clips]

def report():
    root=gs.ROOT;store=GameStore();r=store.recording();scenes=store.scenes(r['id'])
    state=read(root/'Releases/2026-11-13-full-analysis/mission-state.json')
    catalog_path=event_discovery.folder(r)/'catalog.json'
    catalog=read(catalog_path) if catalog_path.exists() else {}
    with store.connect() as db:
        identities=[row[0] for row in db.execute('SELECT id FROM game_batches WHERE recording=? AND index_key=? ORDER BY created',(r['id'],r['index_key']))]
    projects=[]
    for identity in identities:
        batch=store.batch(identity)
        for item in batch['items']:
            p=Path(item['project']);doc=read(p/'edit_plan.json') if (p/'edit_plan.json').exists() else None
            scan=read(p/'story_candidates.json') if (p/'story_candidates.json').exists() else None
            rejection=read(p/'creative_rejection.json') if (p/'creative_rejection.json').exists() else None
            evidence=read(p/'rejected_evidence.json') if (p/'rejected_evidence.json').exists() else None
            old_evidence=evidence
            scan_is_new=bool(scan and evidence and (p/'story_candidates.json').stat().st_mtime_ns>(p/'rejected_evidence.json').stat().st_mtime_ns)
            if scan_is_new and not doc:evidence=None
            if doc:premise=doc['editorial']['premise'];clips=doc['clips']
            elif evidence:premise=evidence['plan']['editorial']['premise'];clips=evidence['plan']['clips']
            elif scan:
                selected=scan['candidates'][scan['selected']];premise=selected['premise'];clips=selected['windows']
            else:premise='Story planning pending';clips=[]
            review=read(p/'creative_review.json') if (p/'creative_review.json').exists() else None
            passed=bool(doc and review and review.get('plan_key')==key(doc) and creative_history.review_passes(review.get('review',{})))
            evidence_proof=read(p/'evidence_review.json') if (p/'evidence_review.json').exists() else None
            evidence_passed=bool(doc and evidence_proof and evidence_proof.get('plan_key')==key(doc))
            q=read(p/'qc_report.json') if (p/'qc_report.json').exists() else None
            actual_pass=bool(q and q.get('status')=='technical_pass' and Path(q.get('output','')).is_file() and digest(q['output'])==q.get('output_sha256'))
            render='not queued'
            job=None
            if item['job']:
                from job_store import JobStore
                job=JobStore(root).get(item['job'])
                status=job['status'];render='queued' if status=='queued' else 'started' if status=='running' else 'failed' if status=='needs_attention' else status
            if actual_pass:render='completed'
            delivered=next((o for o in state.get('outputs',[]) if o['project']==str(p)),None)
            projects.append({'id':p.name,'batch':identity,'batch_status':batch['status'],'project':str(p),
                'premise':premise,'source_ranges':ranges(clips),'scene_ids':[c['scene_id'] for c in clips if c.get('scene_id')],
                'independent_creative_review':'passed' if passed else 'rejected' if rejection else 'pending',
                'originality_rejection_reason':rejection if not passed else None,
                'historical_originality_hold':rejection if passed else None,
                'evidence_review':'passed' if evidence_passed else 'rejected' if evidence else 'pending',
                'evidence_rejection_reason':evidence.get('review') if evidence and not evidence_passed else None,
                'historical_evidence_hold':old_evidence.get('review') if old_evidence and (evidence_passed or scan_is_new) else None,
                'rendering':render,'final_technical_qc':q.get('status') if actual_pass else 'failed_or_stale' if q else 'not run',
                'preview_filename':(delivered['output'] if delivered else q['output']) if actual_pass else None,'job_status':job['status'] if job else None})
    candidates=[]
    for event in catalog.get('events',[]):
        matches=[p for p in projects if set(event['scene_ids']).intersection(p['scene_ids'])]
        passed=[p for p in matches if p['independent_creative_review']=='passed']
        candidate=dict(event,independent_creative_review='passed' if passed else 'rejected' if any(p['originality_rejection_reason'] for p in matches) else 'pending',
            originality_rejection_reason=[p['originality_rejection_reason'] for p in matches if p['originality_rejection_reason']],
            rendering='completed' if any(p['rendering']=='completed' for p in matches) else 'started' if any(p['rendering']=='started' for p in matches) else 'queued' if any(p['rendering']=='queued' for p in matches) else 'failed' if any(p['rendering']=='failed' for p in matches) else 'not queued',
            final_technical_qc='technical_pass' if any(p['final_technical_qc']=='technical_pass' for p in matches) else 'not run',
            preview_filename=next((p['preview_filename'] for p in matches if p['preview_filename']),None),projects=[p['id'] for p in matches])
        candidates.append(candidate)
    reasons=collections.Counter()
    technically_eligible=[]
    for scene in scenes:
        why=event_discovery.eligibility(scene,store)
        if why:reasons.update(why)
        else:technically_eligible.append(scene)
    suitable=[c for c in candidates if c['suitable'] and c['confidence']>=.8]
    confirmed=len({p['id'] for p in projects if p['independent_creative_review']=='passed'})
    with store.connect() as db:reserved={row[0] for row in db.execute('SELECT scene FROM game_shots')}
    unused=[c for c in suitable if not reserved.intersection(c['scene_ids'])]
    result={'updated_utc':now(),'mission_id':state['mission_id'],'mission_stage':state['stage'],
        'spoiler_filtering':config().get('spoiler_filtering',True),'spoiler_warnings':config().get('spoiler_warnings',False),
        'total_observations':len(scenes),'technical_eligible_scenes':len(technically_eligible),
        'distinct_semantic_event_families':len(candidates),'provisionally_suitable_distinct_events':len(suitable),
        'independently_approved_distinct_events':confirmed,'unused_provisional_event_families':len(unused),'observation_rejection_reasons':dict(reasons),
        'semantic_observation_rejections':catalog.get('rejected',[]),'model_metadata_warnings':catalog.get('model_warnings',[]),
        'further_scene_discovery_necessary':len(suitable)<3 if catalog else 'pending semantic catalog',
        'discovery_assessment':'Enough provisional distinct event families for production attempts; independent reviews may still reject them.' if len(suitable)>=3 else 'Insufficient distinct suitable families; targeted cached-proxy discovery needed.',
        'candidates':candidates,'production_attempts':projects,'delivered_outputs':state.get('outputs',[]),'error':state.get('error'),
        'limitations':'Semantic grouping is not independent originality approval. Only actual evidence/history reviews establish candidate approval; only validated final bytes establish technical QC.',
        'publication':'not performed; manual approval required'}
    test_log=(root/'Releases/2026-11-14-expanded-discovery/tests-final.log').read_text(errors='replace')
    smoke=(root/'Releases/2026-11-14-expanded-discovery/render-smoke.log').read_text(errors='replace')
    import re
    counts=re.findall(r'Ran (\d+) tests',test_log)
    result['verification']={'regression_tests':int(counts[-1]) if counts else None,'regression_passed':test_log.rstrip().endswith('OK'),
        'render_smoke_passed':'PASS: actual render' in smoke,'preservation_audit':str(root/'Releases/2026-11-14-expanded-discovery/preservation.json')}
    dest=Path(state['review_folder']);dest.mkdir(exist_ok=True,parents=True)
    prefix='CREATIVE_DISCOVERY_REPORT_'+datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).strftime('%Y%m%d_%H%M%S') if '--snapshot' in sys.argv else 'CREATIVE_DISCOVERY_STATUS'
    save(dest/(prefix+'.json'),result)
    save(root/'Releases/2026-11-14-expanded-discovery/status.json',result)
    lines=['# GamingShorts — expanded creative discovery and production','',
        'Updated: '+datetime.datetime.now(ZoneInfo('Europe/Amsterdam')).isoformat(),
        'Mission: `'+state['mission_id']+'`; stage: `'+state['stage']+'`.','',
        'Spoiler filtering, warning cards and major-spoiler approval are disabled by configuration. Historical labels are retained. Source integrity, copyright/licensing, evidence, originality, QC and manual publication approval remain required.','',
        '| Measure | Count |','| --- | --- |',f'| Existing observations reevaluated | {len(scenes)} |',f'| Technical eligible scenes (including minimum usable duration) | {len(technically_eligible)} |',
        f'| Distinct semantic candidate families | {len(candidates)} |',f'| Provisionally suitable distinct events | {len(suitable)} |',f'| Unused provisional families | {len(unused)} |',f'| Independent creative approvals | {confirmed} |',f"| Delivered Shorts | {len(state.get('outputs',[]))} |",'',
        result['discovery_assessment'],'Semantic families are provisional, not certified unique Shorts. No additional full-source scan is being performed.','',
        '## Rejections by reason','', 'Observation reasons may overlap: '+json.dumps(dict(reasons))+'.',
        f"Semantic observation rejections: {len(catalog.get('rejected',[]))}. Reasons and retained observations are in the JSON companion.",
        f"Metadata warnings (not footage or rejections of real scenes): {len(catalog.get('model_warnings',[]))}.",'',
        '## Production attempts','', '| Candidate / premise | Source timestamps | Independent originality | Evidence | Rendering | Technical QC | Preview |', '| --- | --- | --- | --- | --- | --- | --- |']
    for p in projects:
        source='; '.join(hms(a)+'–'+hms(b) for a,b in p['source_ranges']) or 'pending'
        lines.append('| '+' | '.join(str(x).replace('|','/') for x in (p['premise'],source,p['independent_creative_review'],p['evidence_review'],p['rendering'],p['final_technical_qc'],p['preview_filename'] or 'not available'))+' |')
        if p['originality_rejection_reason']:lines+=['','Originality rejection for '+p['id']+': '+json.dumps(p['originality_rejection_reason']),'']
        if p['evidence_rejection_reason']:lines+=['','Evidence/timing rejection for '+p['id']+': '+json.dumps(p['evidence_rejection_reason']),'']
    lines+=['','## Distinct candidate events','', '| Premise | Source ranges | Suitable (provisional) | Independent creative review | Originality rejection reason | Rendering | Final QC | Preview |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for c in candidates:
        source='; '.join(hms(a)+'–'+hms(b) for a,b in c['source_ranges'])
        lines.append('| '+' | '.join(str(x).replace('|','/') for x in (c['premise'],source,c['suitable'],c['independent_creative_review'],json.dumps(c['originality_rejection_reason']) if c['originality_rejection_reason'] else 'none recorded',c['rendering'],c['final_technical_qc'],c['preview_filename'] or 'not available'))+' |')
    if state.get('error'):lines+=['','Current attention: '+str(state['error'])[:700]]
    lines+=['','## Verification','',f"Regression suite: {result['verification']['regression_tests']} tests; passed: {result['verification']['regression_passed']}.",
        f"FFmpeg fixture render and negative narration control passed: {result['verification']['render_smoke_passed']}. Fixture evidence is separate from actual Cairn final QC.",
        'Preservation audit: `'+result['verification']['preservation_audit']+'`.','']
    lines+=['','No upload/publication has been performed. See `'+prefix+'.json` for full candidate reasons and exact project paths.']
    temporary=dest/(prefix+'.md.tmp');temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8');temporary.replace(dest/(prefix+'.md'))
    print(json.dumps({k:result[k] for k in ('updated_utc','mission_stage','total_observations','technical_eligible_scenes','distinct_semantic_event_families','provisionally_suitable_distinct_events','independently_approved_distinct_events')}),flush=True)

if __name__=='__main__':
    while True:
        report()
        if '--watch' not in sys.argv:break
        time.sleep(45)
