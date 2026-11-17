"""Supply actual caption dwell metadata to the birthday source review once."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,locked
import gaming_shorts as gs
release=gs.ROOT/'Releases/2026-11-14-hybrid-hooks'
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    state=read(release/'state.json')
    if state.get('birthday_caption_schedule_recheck'):raise ValueError('Schedule recheck already attempted; retain any remaining hold')
    item=next(i for i in state['items'] if i['event']=='birthday')
    if item['status']!='blocked' or 'Caption timing' not in item['error']:raise ValueError('Not the diagnosed evidence-window/schedule confusion')
    p=Path(item['project'])
    if list((p/'VoiceVersions').glob('*/voice_generation_attempted.json')):raise ValueError('Voice already attempted; no implicit retry')
    save(release/'birthday_caption_schedule_rejection.json',{'item':item,'review':read(p/'dialogue_editorial_review.json')})
    item.update(status='planning',previous_caption_schedule_rejection=item.pop('error'))
    state['birthday_caption_schedule_recheck']=now();save(release/'state.json',state)
print('Only birthday schedule metadata recheck queued; crystal remains accepted.')
