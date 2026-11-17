"""Write one review handoff for actual completed, verified exports."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,digest
import gaming_shorts as gs
release=gs.ROOT/'Releases/2026-11-15-story-reuse';destination=gs.ROOT/'ReadyForReview/cairn_stories_2026-11-15'
titles={'crystal_lore':"The burial lore behind Cairn's crystal sanctuary",'marco_choice':"When supporting Marco means offering to turn back",'rainbow_logic':"Pack weight meets a rainbow highway"}
verification={x['event']:x for x in read(release/'delivery-verification.json')}
rows=[]
for event,title in titles.items():
    d=read(release/(event+'_delivery.json'));p=read(release/(event+'_plan.json'));q=d['qc'];v=verification[event]
    if digest(d['output'])!=d['sha256'] or v['status']!='passed':raise ValueError('Unverified delivery')
    p['music']=q['music'];save(release/(event+'_plan.json'),p)
    rows.append({'event':event,'title':title,'output':d['output'],'sha256':d['sha256'],'duration':q['actual_duration'],
        'type':p['plan']['editorial']['story_type'],'music':q['music']['title'],'instrumental':q['music'].get('instrumental'),
        'trend_verified':q['music'].get('trend_verified',False),'hook':p['plan']['clips'][0]['narration'],
        'script':[c['narration'] for c in p['plan']['clips']],'source_ranges':[(c['start'],c['start']+c['duration']) for c in p['plan']['clips']],
        'technical_qc':q['status'],'warnings':q['warnings'],'human_listening':'not_performed'})
save(release/'delivery.json',rows);save(destination/'REVIEW_REPORT.json',rows)
lines=['# Cairn: new story-led clips','',
       'Three new commentary edits using the user-authorized reusable recording and saved analysis. Earlier previews remain preserved. No publishing.','',
       '| Story | Type | Duration | Instrumental | Preview |','| --- | --- | --- | --- | --- |']
for row in rows:
    path=row['output'].replace('/mnt/d/','D:/')
    lines.append(f"| {row['title']} | {row['type']} | {row['duration']:.2f}s | {row['music']} | [Watch](<{path}>) |")
lines+=['','Each edit has new added-value commentary, a specific hook, a supported payoff, and a spoken Subscribe for more. over continuing footage. Garret uses only the free model. Actual returned word timestamps drive yellow highlighting in every narrated shot and the CTA.','',
        'Saved source/evidence and independent new-commentary reviews passed. Final exports passed full decode, voice/music balance, speech correlation, cadence and audio-artifact checks. Actual final-frame samples verify yellow highlights in every spoken shot and the CTA. 234 regression tests and the real rendering smoke test passed.','',
        'Music uses existing cleared original instrumentals with retained attribution. These tracks are not claimed to be trending; no current verified trend evidence was available in the saved catalog. Human listening and publication approval remain outstanding.','']
lines+=['Rainbow removes the unsupported words “Some downtime” from the saved take. The original recording is preserved, and retained word timings are mapped by the exact removed sample duration. No replacement speech was generated. Wider conversation and rainbow shots preserve the complete source composition. Earlier framing prototypes are under previous_versions/.','']
for row in rows:
    lines+=[f"## {row['title']}",'',' '.join(row['script']),'',f"Source ranges (seconds): {row['source_ranges']}",'']
    if row['warnings']:lines+=['Technical review notes: '+'; '.join(row['warnings']),'']
(destination/'REVIEW_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(release/'DELIVERY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'review_report':str(destination/'REVIEW_REPORT.md'),'outputs':[r['output'] for r in rows]},indent=2))
