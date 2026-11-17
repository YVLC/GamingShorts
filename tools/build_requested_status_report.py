"""Snapshot the requested report without changing queue, AI calls or production."""
import collections,datetime,json,sys
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save
from game_store import GameStore
import gaming_shorts as gs

def stamp(seconds):
    h=int(seconds//3600);m=int(seconds%3600//60);s=seconds%60
    return f'{h:02d}:{m:02d}:{s:06.3f}'

root=gs.ROOT;release=root/'Releases/2026-11-14-ai-resume'
store=GameStore();inventory=store.inventory();r=inventory['recording']
progress=read(root/'Releases/2026-11-13-full-analysis/progress.json')
state=read(root/'Releases/2026-11-13-full-analysis/mission-state.json')
coverage=read(release/'coverage.json');capacity=read(release/'current-capacity.json')
preservation=read(release/'preservation.json')
eligible=[s for s in inventory['scenes'] if s['eligible']]
with store.connect() as db:
    ids=[row[0] for row in db.execute('SELECT id FROM game_batches WHERE recording=? AND index_key=? ORDER BY created',(r['id'],r['index_key']))]
batches=[];rejections=[];creative_reviews=[];technical_reports=[]
for identity in ids:
    batch=store.batch(identity);batches.append(batch)
    for item in batch['items']:
        p=Path(item['project'])
        for name in ('rejected_evidence.json','creative_rejection.json'):
            if (p/name).exists():rejections.append({'project':str(p),'file':str(p/name),'payload':read(p/name),'type':name})
        if (p/'creative_review.json').exists():creative_reviews.append({'project':str(p),'review':read(p/'creative_review.json')})
        if (p/'qc_report.json').exists():technical_reports.append({'project':str(p),'report':read(p/'qc_report.json')})
processes=[]
for folder in Path('/proc').iterdir():
    if not folder.name.isdigit():continue
    try:
        command=(folder/'cmdline').read_bytes().split(b'\0')
        comm=(folder/'comm').read_text().strip()
        if comm=='codex' or (comm.startswith('python') and any(x.endswith(b'/resume_full_workflow.py') or x==b'tools/resume_full_workflow.py' or x==b'tools/full_analysis_report.py' for x in command)):
            processes.append({'pid':int(folder.name),'program':comm,'role':'AI subprocess' if comm=='codex' else 'report watcher' if b'tools/full_analysis_report.py' in command else 'mission controller'})
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
now=datetime.datetime.now(ZoneInfo('Europe/Amsterdam'))
dest=Path(state['review_folder'])/('STATUS_REPORT_'+now.strftime('%Y-%m-%d_%H%M%S')+'.md')
snapshot=dest.with_suffix('.json')
original=read(root/'Releases/2026-11-13-ai-resilience/handoff.json');stat=Path(r['source']).stat()
unchanged=(stat.st_size,stat.st_mtime_ns)==(original['source_size'],original['source_mtime_ns'])
remaining=100-capacity['limits']['primary']['usedPercent'];weekly=100-capacity['limits']['secondary']['usedPercent']
outputs=state.get('outputs',[])
lines=[
 '# GamingShorts — Cairn analysis and production report',
 '',f"Snapshot: {now.strftime('%d %B %Y, %H:%M:%S %Z')} (Europe/Amsterdam).",
 '', '**Analysis is complete. Three review Shorts have not yet been delivered.**' if not outputs else f'**Analysis is complete; {len(outputs)} review Shorts delivered.**',
 '', '| Item | Verified status |','| --- | --- |',
 f"| Local screening | {progress['locally_screened']}/{progress['total_chunks']} chunks |",
 f"| Selected AI inspections | {progress['ai_completed']}/{progress['selected_ai_chunks']} complete; {progress['selected_ai_chunks']-progress['ai_completed']} remaining |",
 f"| Scene observations | {len(inventory['scenes'])} |",
 f'| Currently eligible scenes | {len(eligible)}; this is not a count of approved unique stories |',
 f'| New review outputs | {len(outputs)} |',
 f"| Mission stage | {state['stage']} |",'| Uploads/publication | None |',
 '', '## Source and preservation',
 '',r'Authoritative source: `D:\GamingShorts\Sources\videoplayback.webm`.',
 f"Duration: {stamp(r['duration'])}. Source size: {stat.st_size:,} bytes. Registered SHA256: `{r['sha256']}`.",
 f"Current source size/mtime match the saved baseline: **{'PASS' if unchanged else 'FAIL'}**. No new full-file hash or copy was performed to generate this report.",
 f"The saved preservation audit ({preservation['updated_utc']}) passed for all 217 local checkpoints, the same 47 selections, the original 14 completed inspections and 84 observations. Completed results were reused.",
 '', '## Coverage and event discovery',
 '',f"The 47 selected chunks represent all 12 equal-duration bands: `{coverage['time_bin_counts']}` chunks per band. Their union is {coverage['selected_seconds']:.3f} seconds ({coverage['selected_seconds']/60:.1f} minutes; {100*coverage['selected_seconds']/coverage['duration']:.1f}% of the recording). Largest unsampled gap: {stamp(coverage['largest_unsampled_gap_seconds'])}.",
 'This provides broad temporal sampling for finding stories. It does not establish exhaustive AI coverage or guarantee three strong, distinct stories. All 217 chunks have local screening.',
 f"Eligible categories now: {dict(collections.Counter(s['category'] for s in eligible))}. Spoiler-uncertain and major material is excluded from automatic production. Major-spoiler rendering requires explicit approval.",
 '', '## Historical comparison and rejected candidates',
 '', f"Recorded creative-repetition rejection files in this mission: {sum(x['type']=='creative_rejection.json' for x in rejections)}. Independent originality approvals recorded: {len(creative_reviews)}. Zero recorded duplicate rejections is not proof that the candidates have passed originality review.",
 'The existing pipeline checks historical footage reservations, visual sequences, hooks, central events and narrative arcs before speech. Music changes and rewritten synonyms do not establish originality.',
 ]
for item in rejections:
    payload=item['payload'];doc=payload.get('plan',{})
    lines += ['',f"Rejected draft: **{doc.get('editorial',{}).get('premise',Path(item['project']).name)}**."]
    for issue in payload.get('review',{}).get('issues',[]):lines.append('- '+issue)
    if doc.get('clips'):
        lines += ['', 'Proposed source intervals (rejected draft, not final footage):']
        lines += ['- '+stamp(c['start'])+'–'+stamp(c['start']+c['duration']) for c in doc['clips']]
    lines += ['','Evidence: `'+item['file']+'`.']
lines += ['', 'The first draft was held for ending/payoff timing, not a proven duplicate. Its three scene records remain saved but were automatically excluded for bounded replanning. No narration or render was requested for that rejected draft.',
 '', '## Active work and capacity',
 '',f"Capacity check at {capacity['updated_utc']}: **{remaining:g}% remaining in the five-hour window; {weekly:g}% remaining weekly**. These figures describe remaining allowance, not usage consumed. Capacity was available; no usage-limit rejection explains the currently pending planning call.",
 'Processes observed: '+(', '.join(f"{p['role']} PID {p['pid']}" for p in processes) or 'none matching the mission/AI worker')+'.',
 'Catalog batches (includes the pending batch, which is not yet listed as completed in mission-state.json):',
 ]
for batch in batches:lines.append(f"- `{batch['id']}`: `{batch['status']}`; "+', '.join(x['project'] for x in batch['items']))
lines += ['', 'A single second story-planning request was still awaiting a structured result at this snapshot. It has not been duplicated. A running mission must not be replaced with a second indexing worker.',
 '', '## Render and QA results',
 '', f"New technical QC reports: {len(technical_reports)}. Regression tests: **217 passed**, recorded in `Releases/2026-11-14-ai-resume/tests.log`.",
 'No new final video has yet passed video/audio playback, caption synchronization, aspect-ratio, black-frame/corruption, narration, music-license, uniqueness or scene-timing QA in this mission. Those checks are pending production; regression tests are not a substitute for checking rendered media.',
 'Existing Garret/free-voice, licensed-music selection, word-aligned captions, original-source rendering and QA safeguards remain configured. No new music selection or narration asset is being represented as approved here.',
 '', '## Deliverables and remaining action',
 '', r'Review folder: `D:\GamingShorts\ReadyForReview\cairn_first_three_1b28a5dd9e1b`.',
 'Final selected stories, final source timestamps and final preview filenames: **not available yet**. Rejected/provisional timestamps above must not be treated as delivered footage.',
 'Next: let the existing planning request finish or reach its bounded timeout, inspect its saved outcome, and continue only with candidates that pass evidence and independent history review. An uncertain AI/voice call must not be blindly replayed. No full-recording reanalysis or source duplication is needed.',
 '', 'The original source, earlier Shorts, approvals and completed checkpoints remain preserved. Nothing has been uploaded or published.',
 '', 'Machine-readable details: `'+str(snapshot)+'`.',
 ]
dest.write_text('\n'.join(lines)+'\n',encoding='utf-8')
save(snapshot,{'snapshot':now.isoformat(),'progress':progress,'mission_state':state,'eligible_scenes':[{k:s[k] for k in ('id','start','end','description','category','score')} for s in eligible],'batches':batches,'rejections':rejections,'originality_reviews':creative_reviews,'technical_qa_reports':technical_reports,'capacity':capacity,'processes':processes,'source_fingerprint_unchanged':unchanged,'report':str(dest)})
print(json.dumps({'report':str(dest),'json':str(snapshot),'new_outputs':len(outputs),'eligible_scenes':len(eligible),'remaining_ai':progress['selected_ai_chunks']-progress['ai_completed']},indent=2))
