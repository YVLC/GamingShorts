"""Presentation-only repair: keep both sides of the conversation visible."""
import sys,copy,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,locked
import gaming_shorts as gs,game_plan,story_policy,creative_history,shared_index
from game_index import cached_ai

release=gs.ROOT/'Releases/2026-11-15-story-reuse'
event=sys.argv[1] if len(sys.argv)>1 else 'marco_choice'
if event not in ('marco_choice','rainbow_logic'):raise ValueError('Unknown framing revision')
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    meta=read(release/(event+'_plan.json'));p=Path(meta['project']);old=read(p/'edit_plan.json');doc=copy.deepcopy(old)
    for c in (doc['clips'][1:] if event=='marco_choice' else doc['clips']):c['framing']='blur_contain'
    if doc==old:print('Wider framing already applied');raise SystemExit(0)
    archive=p/'PresentationRevisions/before_wider_conversation';archive.mkdir(parents=True,exist_ok=True)
    for name in ('edit_plan.json','evidence_review.json','creative_review.json','qc_report.json'):
        if (p/name).exists() and not (archive/name).exists():shutil.copy2(p/name,archive/name)
    prototypes=release/'framing_prototypes';prototypes.mkdir(exist_ok=True)
    if not (prototypes/(event+'_delivery.json')).exists():shutil.copy2(release/(event+'_delivery.json'),prototypes/(event+'_delivery.json'))
    images=[shared_index.dense(p,c['start'],c['duration']) for c in doc['clips']]
    import voices,captions
    voice=p/read(p/'active_voice.json')['folder'];aligned=captions._from_saved_heygen_words(voice,doc['clips']);placements=[]
    for i,c in enumerate(doc['clips']):
        spoken=gs.duration(voice/'Voices'/f'line_{i+1:02d}.wav');delay=max(.05,c['duration']-spoken-.1) if i==len(doc['clips'])-1 else min(.15,max(.05,(c['duration']-spoken)/2))
        placements.append({'clip':i+1,'clip_source_start':c['start'],'actual_first_spoken_word_source_time':c['start']+delay+aligned['lines'][i]['words'][0]['start']})
    review=cached_ai(p/'PresentationReview',story_policy.BRIEF+' Independently review the SOURCE FACTS AND SCRIPT ONLY against these timestamped original-source windows. The same source intervals and existing voice are retained while wide framing will preserve the complete source composition. Narration should add value rather than read subtitles, pay off the hook and close with CTA after payoff. immediate_action means an immediate compelling hook. This is a pre-render source/script review: rendered framing, audio performance, caption timing and music rights are tested separately after rendering, not asserted by this review. Do not pretend to see or hear final media. List actual source/script defects as issues; the absence of final-media evidence is a scope limitation, not a source/script defect. Preserve any real unsupported claim or uncertainty as a rejection. IMPORTANT: speech does not necessarily start at the clip source start. Use the supplied actual placement map derived from saved audio and returned word timestamps; the final sentence is placed near the end of its shot. No tools. Return schema JSON. Plan: '+json.dumps(doc)+' Actual speech placement: '+json.dumps(placements),game_plan.REVIEW,images,'wider_timed_source_review')
    if not story_policy.review_passes(review):raise ValueError('Wider-layout review failed: '+json.dumps(review))
    creative_history.require_review(p,doc,invoke=True,images=images)
    receipt=read(p/'evidence_review.json');receipt.update(plan_key=key(doc),story_identity=story_policy.receipt_identity(p,doc),review=review)
    save(p/'evidence_review.json',receipt);save(p/'edit_plan.json',doc)
    meta['plan']=doc;save(release/(event+'_plan.json'),meta)
    print('Wider conversation framing reviewed; exact narration retained',flush=True)
