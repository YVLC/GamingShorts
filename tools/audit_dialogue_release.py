"""Read-only preservation checks and a consistent, versioned release snapshot."""
import sys,sqlite3,zipfile,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,digest,now,locked
from dialogue_mission import release,state_path
import dialogue_editorial as policy,gaming_shorts as gs
from game_store import GameStore
root=gs.ROOT;dest=release();store=GameStore()
with locked(root/'Database/.full_analysis_mission.lock'):
    state=read(state_path());checks={}
    with sqlite3.connect(dest/'before.sqlite3') as before,store.connect() as current:
        for table in ('game_chunks','game_scenes','game_recordings','game_local_screens_v1','game_ai_selection_v1'):
            old=before.execute('SELECT * FROM '+table).fetchall()
            live={tuple(row) for row in current.execute('SELECT * FROM '+table)}
            checks[table]={'before':len(old),'after':len(live),'all_previous_rows_unchanged':all(tuple(row) in live for row in old)}
            if not checks[table]['all_previous_rows_unchanged']:raise ValueError('Historical evidence changed: '+table)
        r=store.recording()
        checks['active_index']={name:current.execute('SELECT count(*) FROM '+table+' WHERE recording=? AND index_key=?',(r['id'],r['index_key'])).fetchone()[0] for name,table in (('local_screens','game_local_screens_v1'),('selected_ai','game_ai_selection_v1'),('observations','game_scenes'))}
        assert checks['active_index']=={'local_screens':217,'selected_ai':47,'observations':260}
        with sqlite3.connect(dest/'after.sqlite3') as backup:current.backup(backup)
    original=root/'Sources/videoplayback.webm';stat=original.stat()
    baseline=read(root/'Releases/2026-11-13-ai-resilience/handoff.json')
    checks['source_stat']={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,'expected_bytes':63959292291,'expected_mtime_ns':1794515665479289100}
    assert stat.st_size==63959292291 and stat.st_mtime_ns==1794515665479289100,'Original recording changed'
    with zipfile.ZipFile(dest/'before-runtime.zip') as before_code:
        old_adapter=before_code.read('Automation/gamingshorts_v2/editorial.py')
    checks['index_identity_adapter_unchanged']=hashlib.sha256(old_adapter).hexdigest()==digest(root/'Automation/gamingshorts_v2/editorial.py')
    assert checks['index_identity_adapter_unchanged']
    robot=root/'Projects/V2/videoplayback_e772d2c8_game_af978f310d6b3fbcb224_1'
    old_q=read(robot/'qc_report.json');checks['previous_robot_output_preserved']=digest(old_q['output'])==old_q['output_sha256']
    assert checks['previous_robot_output_preserved']
    checks['delivered']=[]
    for item in state['candidates']:
        if item['status']!='technical_pass':continue
        p=Path(item['project']);q=read(p/'qc_report.json');plan=read(p/'edit_plan.json');review=read(p/'portrait_editorial_review.json')
        assert policy.completed(p),'Stale render fingerprint'
        assert policy.review_passes(review,plan['editorial']['mode']),'Editorial hold'
        assert digest(item['preview'])==q['output_sha256'],'Review copy differs'
        assert not q['errors'] and q['music']['usage_route']=='cleared' and q['music']['instrumental']
        checks['delivered'].append({'event':item['event_id'],'path':item['preview'],'sha256':q['output_sha256'],'duration':q['actual_duration'],'technical_qc':q['status'],'portrait_editorial_score':review['score'],'music':q['music']['title'],'license_evidence':q['music']['license_evidence'],'original_source':q['visual_quality']['proxy_rendering'] is False})
    checks.update(created_utc=now(),no_publishing_called=True,limitations='Human playback/editorial approval still required; automated audio metrics do not establish subjective listening quality.')
    save(dest/'preservation-and-delivery.json',checks)
    with zipfile.ZipFile(dest/'after-runtime.zip','w',zipfile.ZIP_DEFLATED) as z:
        for folder in ('Automation/gamingshorts_v2','tools','docs'):
            for p in (root/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(root))
    save(dest/'release-manifest.json',{'created_utc':now(),'files':{p.name:digest(p) for p in (dest/'after-runtime.zip',dest/'after.sqlite3',dest/'preservation-and-delivery.json')}})
    print(json.dumps(checks,indent=2))
