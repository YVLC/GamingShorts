"""Read-only progress/reporting companion. No analysis, speech or publication calls."""
from pathlib import Path
import sys,json,time,sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now
import gaming_shorts as gs

folder=gs.ROOT/'Releases/2026-11-13-full-analysis'
def report():
    state=read(folder/'mission-state.json');progress=read(folder/'progress.json') if (folder/'progress.json').exists() else {}
    db=sqlite3.connect(gs.ROOT/'Database/editorial_v2.sqlite3');db.row_factory=sqlite3.Row
    r=db.execute('SELECT * FROM game_recordings WHERE id=?',(progress.get('recording'),)).fetchone()
    scenes=[dict(x) for x in db.execute('SELECT id,start,end,description,category,spoiler,rejected,confidence,score FROM game_scenes WHERE recording=? AND index_key=?',(r['id'],r['index_key']))] if r else []
    rejections=[]
    for batch in state.get('batches',[]):
        for item in db.execute('SELECT project FROM game_batch_items WHERE batch=?',(batch,)):
            p=Path(item['project'])
            for name in ('creative_rejection.json','rejected_evidence.json'):
                if (p/name).exists():rejections.append({'project':str(p),'evidence':str(p/name),'details':read(p/name)})
    db.close()
    summary={'updated_utc':now(),'stage':state['stage'],'analysis':progress,'scenes':scenes,'rejected_creative_candidates':rejections,'outputs':state.get('outputs',[]),'error':state.get('error'),'publication':'not performed'}
    save(folder/'completion-report.json',summary)
    dest=Path(state['review_folder']);dest.mkdir(exist_ok=True,parents=True)
    lines=['# Full Cairn analysis and review report','','Stage: '+state['stage'],'',f"Chunks locally screened: {progress.get('locally_screened',0)}/{progress.get('total_chunks',217)}",f"AI-inspected chunks: {progress.get('ai_completed',0)}",f'Discovered scene observations: {len(scenes)}',f'Creative rejection records: {len(rejections)}',f"Valid delivered Shorts: {len(state.get('outputs',[]))}",'','No publication has been performed. Source recording is retained in place.','']
    if state.get('error'):lines+=['Attention: '+state['error'],'']
    for i,out in enumerate(state.get('outputs',[]),1):
        lines += [f'## Short {i}: '+out['title'],'','Narrative: '+out['summary'],'','Original source timestamps: '+json.dumps(out['ranges']),'Duration: '+str(out['duration']),'Spoiler: '+out['spoiler'],'QA: '+out['qa'],'Output: '+out['output'],'Creative evidence: '+out['creative_review'],'']
    lines+=['## Tests','','Regression evidence: '+str(folder/'tests-final.log'),'The earlier bounded pilot passed proxy coverage, source paths, checkpoint reuse and actual AI adapter response validation.','Semantic observations are sampled, not exhaustive understanding of the full game.','']
    (dest/'ANALYSIS_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return state['stage']
if __name__=='__main__':
    while True:
        stage=report()
        if '--watch' not in sys.argv or stage in ('complete','complete_fewer_than_three_valid_stories','needs_attention'):break
        time.sleep(30)
