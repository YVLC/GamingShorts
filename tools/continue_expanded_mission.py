"""Resume the same mission with changed policy; never retry old uncertain inputs."""
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import locked,read,save,now,config,key
import gaming_shorts as gs,event_discovery
from game_store import GameStore

root=gs.ROOT;release=root/'Releases/2026-11-14-expanded-discovery'
with locked(root/'Database/.full_analysis_mission.lock'):
    store=GameStore()
    backup=release/'before/editorial_v2.sqlite3'
    if not backup.exists():
        with store.connect() as db:
            with sqlite3.connect(backup) as dest:db.backup(dest)
    catalog=event_discovery.build()
    save(release/'catalog.json',catalog)
    state=read(root/'Releases/2026-11-13-full-analysis/mission-state.json')
    incomplete=[store.batch(i) for i in state['batches'] if store.batch(i)['status']=='needs_attention']
    if incomplete:
        if len(incomplete)!=1:raise RuntimeError('More than one held batch requires inspection')
        batch=incomplete[0]
        if any(i['job'] or (Path(i['project'])/'edit_plan.json').exists() for i in batch['items']):raise RuntimeError('Production or speech already started; no automatic retry')
        requests=[]
        for item in batch['items']:
            for request in (Path(item['project'])/'FullGameAnalysis').glob('*/request.json'):
                if not (request.parent/'verified.json').exists():requests.append(str(request))
        save(root/'Releases/2026-11-13-full-analysis/expanded-policy-resume.json',
             {'batch':batch['id'],'status':'authorized_new_policy','updated_utc':now(),'config_key':key(config()),
              'catalog_key':catalog['policy_key'],'old_uncertain_requests_preserved':requests,
              'reason':'User disabled spoiler filtering and authorized expanded candidate discovery. New prompts/candidates; old uncertain request is not replayed.'})
    save(release/'resume-receipt.json',{'updated_utc':now(),'mission_id':state['mission_id'],'event_families':len(catalog['events']),
        'provisionally_suitable':sum(e['suitable'] and e['confidence']>=.8 for e in catalog['events'])})
import resume_full_workflow
resume_full_workflow.main()
