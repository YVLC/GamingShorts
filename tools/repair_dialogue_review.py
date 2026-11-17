"""One scoped caption correction and policy-aware reassessment; no TTS retry."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now,locked
import gaming_shorts as gs
from dialogue_mission import release,state_path,continue_mission
root=gs.ROOT
with locked(root/'Database/.full_analysis_mission.lock'):
    path=release()/'comparison.json';comparison=read(path)
    archive=release()/'ComparisonHistory';archive.mkdir(exist_ok=True)
    previous=archive/(key(comparison)+'.json')
    if not previous.exists():save(previous,comparison)
    changed=[]
    for event in comparison['evidence']['events']:
        if event['event_id']!='birthday':continue
        for line in event['dialogue']:
            if line['text']=="I hope you remembered to take candles up there.":
                changed.append({'old_text':line['text'],'new_text':"I hope you remembered to take candles up there!",'reason':'Independent original-frame review verified the source exclamation mark','updated_utc':now()})
                line['text']="I hope you remembered to take candles up there!"
    comparison.setdefault('source_transcription_corrections',[]).extend(changed);save(path,comparison)
    state=read(state_path())
    for item in state['candidates']:
        if item['event_id'] not in ('crystal','birthday') or item['status']!='held':continue
        p=Path(item['project'])
        if (p/'active_voice.json').exists() or (p/'qc_report.json').exists():raise RuntimeError('Existing voice/render needs inspection; no blind retry')
        item.update(status='not queued',quality='pending',originality='pending',previous_hold=item.get('error'))
        item.pop('error',None)
    save(state_path(),state)
continue_mission()
