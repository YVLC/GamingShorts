"""Verify reset, preserve the definite rejected attempt, resume the existing mission."""
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
import ai_capacity,game_index,local_index,gaming_shorts as gs
from common import read,save,now,locked
from game_store import GameStore
ROOT=gs.ROOT
release=ROOT/'Releases/2026-11-14-ai-resume'

def inspect(recover=False):
    release.mkdir(parents=True,exist_ok=True)
    store=GameStore();r=store.recording()
    with store.connect() as db:
        selected=[dict(zip(('ordinal','start','end','status'),row)) for row in db.execute('SELECT c.ordinal,c.start,c.end,c.status FROM game_ai_selection_v1 s JOIN game_chunks c USING(recording,index_key,ordinal) WHERE s.recording=? AND s.index_key=? ORDER BY c.ordinal',(r['id'],r['index_key']))]
        local_count=db.execute('SELECT count(*) FROM game_local_screens_v1 WHERE recording=? AND index_key=?',(r['id'],r['index_key'])).fetchone()[0]
        scenes=[dict(zip(('id','start','end','description','category','spoiler','rejected','confidence','score'),row)) for row in db.execute('SELECT id,start,end,description,category,spoiler,rejected,confidence,score FROM game_scenes WHERE recording=? AND index_key=? ORDER BY start',(r['id'],r['index_key']))]
        if recover:
            with sqlite3.connect(release/'before/editorial_v2.sqlite3') as snapshot:db.backup(snapshot)
    merged=[]
    for x in selected:
        if merged and x['start']<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],x['end'])
        else:merged.append([x['start'],x['end']])
    bins=[sum(min(11,int(x['start']/r['duration']*12))==i for x in selected) for i in range(12)]
    cursor=0;gaps=[]
    for a,b in merged:
        if a>cursor:gaps.append([cursor,a])
        cursor=max(cursor,b)
    if cursor<r['duration']:gaps.append([cursor,r['duration']])
    report={'updated_utc':now(),'locally_screened':local_count,'selected':len(selected),'ai_completed':sum(x['status']=='complete' for x in selected),'remaining':sum(x['status']!='complete' for x in selected),'time_bin_counts':bins,'selected_seconds':sum(b-a for a,b in merged),'duration':r['duration'],'largest_unsampled_gap_seconds':max((b-a for a,b in gaps),default=0),'selection':selected,'scene_observations':len(scenes),'scenes':scenes,'coverage_assessment':'All 12 temporal bins represented; stratified candidate sampling supports story discovery, not exhaustive semantic coverage.' if all(bins) else 'Temporal sampling gaps require assessment before claiming full-recording candidate coverage.'}
    if recover:
        limits=ai_capacity.capacity_read()
        if not ai_capacity.available(limits):raise RuntimeError('No confirmed AI capacity; no generation started')
        folder=ROOT/'FootageIndex'/('sha256_'+r['sha256'])/('LocalFirst_'+r['index_key'][:16])
        recovered=[]
        for request in folder.glob('chunk_*/event_inspection_*/request.json'):
            call=request.parent
            if (call/'verified.json').exists():continue
            log=call/'event_inspection.log';candidate=call/'event_inspection.candidate.json'
            if not log.exists():continue
            errors=[line for line in log.read_text(errors='replace').splitlines() if line.startswith('ERROR:')]
            if not any(ai_capacity.quota_failure(line) for line in errors):continue
            if candidate.exists() and candidate.read_bytes().strip():raise RuntimeError('Nonempty uncertain AI output requires inspection: '+str(call))
            save(call/'capacity_deferred.json',{'request_key':read(request)['request_key'],'reason':'Inspected definite quota rejection after usage reset','saved_utc':now()})
            recovered.append(str(call))
        ai_capacity.persist({'blocked':False,'updated_utc':now(),'reason':'Fresh read-only capacity confirmation after reset','next_check':0})
        report.update(recovered_quota_requests=recovered,capacity=limits.get('rateLimits'))
    save(release/'coverage.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('selection','scenes')},indent=2),flush=True)
    return report

if __name__=='__main__':
    if '--resume' in sys.argv:
        # A running mission holds this lock. Never create a second worker.
        with locked(ROOT/'Database/.full_analysis_mission.lock'):inspect(recover=True)
        import resume_full_workflow
        resume_full_workflow.main()
    else:inspect()
