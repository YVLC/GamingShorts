"""Remove two unsupported transition words from saved speech; no synthesis."""
import sys,copy,shutil,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,digest,run,locked
import gaming_shorts as gs,voices,captions

release=gs.ROOT/'Releases/2026-11-15-story-reuse'
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    meta=read(release/'rainbow_logic_plan.json');p=Path(meta['project']);doc=read(p/'edit_plan.json')
    if not doc['clips'][2]['narration'].startswith('Some downtime later'):
        print('Transition already corrected');raise SystemExit(0)
    old_folder=p/read(p/'active_voice.json')['folder'];old_proof=read(old_folder/'provenance.json');raw=read(old_folder/'voice_result.json');master=old_folder/'Audio/heygen_full.wav'
    archive=p/'PresentationRevisions/before_transition_word_trim';archive.mkdir(parents=True,exist_ok=True)
    for name in ('edit_plan.json','active_voice.json','evidence_review.json','creative_review.json','qc_report.json'):
        if (p/name).exists() and not (archive/name).exists():shutil.copy2(p/name,archive/name)
    new=copy.deepcopy(doc);new['clips'][2]['narration']='Later'+new['clips'][2]['narration'][len('Some downtime later'):]
    index=sum(len(captions.tokens(c['narration'])) for c in doc['clips'][:2]);words=raw['words']
    if [captions.tokens(w['word']) for w in words[index:index+3]]!=[['some'],['downtime'],['later']]:raise ValueError('Unexpected source words')
    rate=int(next(s for s in gs.probe(master)['streams'] if s['codec_type']=='audio')['sample_rate'])
    lo=round((words[index]['start']-.035)*rate);hi=round((words[index+2]['start']-.035)*rate);removed=(hi-lo)/rate
    request=voices.request(new['clips']);folder=p/'VoiceVersions'/key(request);(folder/'Audio').mkdir(parents=True,exist_ok=True);target=folder/'Audio/heygen_full.wav'
    mapping={'origin':'existing_master_word_trim','source_folder':str(old_folder),'source_master_sha256':digest(master),'source_request':old_proof['request'],
             'final_request':request,'removed_words':['Some','downtime'],'removed_source_samples':[lo,hi],'source_sample_rate':rate,'removed_seconds':removed,
             'boundary_fades':'5 ms wholly within the 35 ms pre-word margins; no speech speed change','timing':'Real returned word intervals; retained later words shifted by exact removed sample duration'}
    save(folder/'derived_master_edit.json',mapping)
    if not target.exists():
        graph=f'[0:a]atrim=end_sample={lo},asetpts=PTS-STARTPTS,afade=t=out:st={lo/rate-.005}:d=0.005[a];[0:a]atrim=start_sample={hi},asetpts=PTS-STARTPTS,afade=t=in:d=0.005[b];[a][b]concat=n=2:v=0:a=1[out]'
        run(['ffmpeg','-v','error','-nostdin','-y','-i',master,'-filter_complex',graph,'-map','[out]','-c:a','pcm_f32le',target])
    kept=[dict(w,start=w['start']-removed if n>=index+2 else w['start'],end=w['end']-removed if n>=index+2 else w['end']) for n,w in enumerate(words) if n not in (index,index+1)]
    result=dict(raw,words=kept,duration_seconds=gs.duration(target),derivation=mapping);phrases=[];cursor=0
    for n,c in enumerate(new['clips'],1):
        count=len(captions.tokens(c['narration']));part=kept[cursor:cursor+count];cursor+=count
        phrases.append({'index':n,'first_word_start':part[0]['start'],'last_word_end':part[-1]['end']})
    result['phrases']=phrases;result['cta_start_seconds']=next(w['start'] for w in kept if captions.tokens(w['word'])==['subscribe'])
    captions.validate_words(kept,' '.join(request['lines']),result['duration_seconds']);save(folder/'voice_result.json',result)
    verified=voices.ensure(p,new['clips']);proof=read(verified/'provenance.json');proof.update(origin='existing_master_word_trim',derived_from=str(old_folder.relative_to(p)),derivation=mapping)
    save(verified/'provenance.json',proof);captions._from_saved_heygen_words(verified,new['clips'])
    save(p/'edit_plan.json',new);meta.update(plan=new,speech_request=request);save(release/'rainbow_logic_plan.json',meta)
    print('Removed two words from saved speech; new text/audio/timing provenance retained, no HeyGen call.',flush=True)
