"""Prepare/import one explicitly free Garret MCP result; never synthesizes."""
import sys,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,now
import voices,captions
import gaming_shorts as gs

release=gs.ROOT/'Releases/2026-11-15-batch-three'
parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','import']);parser.add_argument('event');args=parser.parse_args()
plan=read(release/(args.event+'_plan.json'));p=Path(plan['project']);clips=plan['plan']['clips'];request=voices.request(clips)
folder=p/'VoiceVersions'/key(request);folder.mkdir(parents=True,exist_ok=True)
marker=folder/'voice_generation_attempted.json'
if args.stage=='prepare':
    if marker.exists():raise ValueError('Speech attempt already recorded; recover the saved outcome, never blindly retry')
    save(folder/'submitted_request.json',request)
    save(marker,{'started_utc':now(),'voice_id':request['voice_id'],'model':request['model'],'status':'MCP request prepared; no retry without known outcome'})
    print(json.dumps(dict(text=' '.join(request['lines']),voiceId=request['voice_id'],model=request['model'],language='en',expressivenessBoost=1,withTimestamps=True)))
else:
    raw=read(release/(args.event+'_speech.json'))
    words=[{'word':w['text'],'start':w['start_time'],'end':w['end_time']} for w in raw['original_words']]
    captions.validate_words(words,' '.join(request['lines']),raw['duration'])
    phrases=[];index=0
    for n,line in enumerate(request['lines'],1):
        count=len(captions.tokens(line));part=words[index:index+count];index+=count
        phrases.append({'index':n,'first_word_start':part[0]['start'],'last_word_end':part[-1]['end']})
    subscribe=[w['start'] for w in words if captions.tokens(w['word'])==['subscribe']]
    result={'audio_url':raw['audio_url'],'duration_seconds':raw['duration'],'voice_id':request['voice_id'],'model':request['model'],'words':words,'phrases':phrases,'cta_start_seconds':subscribe[-1] if subscribe else -1}
    if (folder/'voice_result.json').exists() and read(folder/'voice_result.json')!=result:raise ValueError('Saved speech result conflicts')
    save(folder/'voice_result.json',result)
    # Reuse standard download, sample-accurate splitting and byte provenance.
    verified=voices.ensure(p,clips)
    alignment=captions._from_saved_heygen_words(verified,clips)
    print(json.dumps({'event':args.event,'voice_folder':str(verified),'lines':len(alignment['lines'])}))


