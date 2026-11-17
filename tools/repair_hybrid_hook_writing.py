"""One bounded editorial rewrite, only before any voice request for either hook."""
import sys,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,key,locked
import gaming_shorts as gs,dialogue_mission as mission,editorial
from game_index import cached_ai
release=gs.ROOT/'Releases/2026-11-14-hybrid-hooks'
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    state=read(release/'state.json')
    if state.get('bounded_hook_rewrite'):raise ValueError('Single rewrite already attempted; retain any remaining rejection')
    images=[]
    for item in state['items']:
        if item['status']!='blocked' or not item['error'].startswith('Dialogue/storytelling review rejected'):raise ValueError('Only definite pre-speech editorial rejections may be rewritten')
        p=Path(item['project'])
        if list((p/'VoiceVersions').glob('*/voice_generation_attempted.json')):raise ValueError('Voice attempt exists; no implicit speech retry')
        images+=mission.exact_images(p,{'start':item['choice']['start'],'duration':item['choice']['duration']})
    schema=editorial.obj({'hooks':{'type':'array','minItems':2,'maxItems':2,'items':editorial.obj({'event':{'type':'string','enum':['crystal','birthday']},'commentary':editorial.S,'added_value':editorial.S,'rationale':editorial.S})}})
    prompt=('Rewrite these two definitively rejected, not-yet-spoken hooks ONCE. User requests a humorous external narrator hook, real Garret speech and yellow captions. '
        'Each hook must be 6–10 words and add a new joke or commentator perspective, without summarizing, revealing or paraphrasing the dialogue payoff. '
        'Do not invent treasure hunting, lore, game choices or mechanics. Clearly figurative juxtaposition is allowed; the narrator is not a game character. '
        'For crystal, consider a contrast between climbing expectations and an unexpected philosophical conversation, without naming the cemetery or the ethics question. '
        'For birthday, consider the contrast between physical expedition hazards and dealing with friends, without mentioning birthdays, distance, absence or party etiquette. '
        'An example direction, not mandatory wording: friends as the one hazard you cannot train for; climbing guides failing to cover philosophy homework. '
        'The silent source lower subtitle UI is cropped out in actual portrait output. Only the verified main dialogue is re-typeset after the hook. No competing intro source subtitles will be shown. '
        'Keep it witty and natural, not generic cliffhangers. Previous requests and concrete rejection reasons: '+json.dumps(state['items'])+'. No tools. Return schema JSON.')
    result=cached_ai(release,prompt,schema,images,'bounded_hook_rewrite')
    if {h['event'] for h in result['hooks']}!={'crystal','birthday'}:raise ValueError('Wrong event set')
    save(release/'before_hook_rewrite.json',state)
    for item in state['items']:
        h=next(h for h in result['hooks'] if h['event']==item['event'])
        if not 6<=len(h['commentary'].split())<=10:raise ValueError('Hook does not fit the brief lead-in')
        item['choice'].update(commentary=h['commentary'],added_value=h['added_value'],narration_rationale=h['rationale'])
        item.update(status='planning',previous_editorial_rejection=item.pop('error'))
    state['bounded_hook_rewrite']=now();save(release/'state.json',state)
print('Bounded rewrite saved; no speech requested by this helper.')
