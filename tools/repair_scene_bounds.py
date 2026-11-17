"""One bounded correction of a definite, completed but invalid AI response."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
from game_store import GameStore
import game_index as index,local_index,gaming_shorts as gs

def repair(ordinal):
    store=GameStore()
    with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
        r=store.recording()
        folder=gs.ROOT/'FootageIndex'/('sha256_'+r['sha256'])/('LocalFirst_'+r['index_key'][:16])
        item=next(x for x in local_index.chunks(store,r) if x['ordinal']==ordinal)
        if item['status']=='complete':print('Already complete; no AI request');return
        dest=folder/f'chunk_{ordinal:05d}'
        receipts=list(dest.glob('event_inspection_*/verified.json'))
        if len(receipts)!=1:raise ValueError('Expected exactly one original completed response')
        result=read(receipts[0])['result']
        a,b=item['start'],item['end']
        try:index.validate_scenes(result,r,ordinal,a,b,dest,r['index_key'])
        except ValueError as error:reason=str(error)
        else:raise ValueError('Original result is valid; repair is unnecessary')
        artifacts=read(dest/'artifacts.json')
        images=[dest/name for name in artifacts['files'] if name.endswith('.jpg')]
        prompt=(f'Reinspect ONLY the actual attached source frames in absolute interval [{a},{b}] seconds. '
            'A prior completed response failed strict validation: '+reason+'. '
            'The earlier proposed scenes are untrusted suggestions, not evidence. '
            'Every start and end MUST be within this exact interval, every scene lasts at least 2 seconds, '
            'and each assertion must have direct support from the timestamped images. '
            'Do not invent or shift timestamps. Omit unsupported/out-of-range scenes; an empty list is allowed. '
            'Classify ordinary gameplay positively as none only when supported, otherwise possible/major. '
            'Tag bridges and static/menu material honestly. No tools, commands or lore inference. '
            'Return schema JSON. Prior rejected response: '+json.dumps(result))
        corrected=index.cached_ai(dest,prompt,index.SCHEMA,images,'event_bounds_correction')
        rows=index.validate_scenes(corrected,r,ordinal,a,b,dest,r['index_key'])
        index.checked_recording(r)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows:db.execute('INSERT OR IGNORE INTO game_scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',row)
            db.execute("UPDATE game_chunks SET status='complete',error=NULL WHERE recording=? AND index_key=? AND ordinal=?",(r['id'],r['index_key'],ordinal))
        save(dest/'bounds_correction.json',{'original_receipt':str(receipts[0]),'original_result_key':key(result),'corrected_result_key':key(corrected),'reason':reason,'scenes_committed':len(rows),'updated_utc':now()})
        local_index.progress(store,r,'event_inspection',{'selected_ai_chunks':47})
        print('Corrected and committed',len(rows),'bounded scenes',flush=True)

if __name__=='__main__':repair(int(sys.argv[1]))
