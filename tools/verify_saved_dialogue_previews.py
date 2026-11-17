"""Revalidate existing accepted media and evidence without AI or new renders."""
import sys,subprocess,json,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,digest,now
from dialogue_mission import state_path,release
import dialogue_editorial as policy,quality_checks
from game_store import GameStore
dest=release()/'checkpoint_reverification';dest.mkdir(exist_ok=True)
state=read(state_path());results=[];recording=GameStore().recording()
stat=Path(recording['source']).stat()
assert stat.st_size==63959292291 and stat.st_mtime_ns==1794515665479289100
for item in state['candidates']:
    if item['event_id'] not in ('crystal','birthday'):continue
    assert item['status']=='technical_pass'
    p=Path(item['project']);doc=read(p/'edit_plan.json');q=read(p/'qc_report.json');manifest=read(p/'manifest.json')
    policy.validate(doc,manifest);assert policy.completed(p),'Saved render inputs changed'
    assert manifest['source']==recording['source'] and not q['visual_quality']['proxy_rendering']
    evidence=read(p/'dialogue_editorial_review.json');creative=read(p/'creative_review.json');portrait=read(p/'portrait_editorial_review.json')
    assert evidence['plan_key']==key(doc)==creative['plan_key']
    assert policy.review_passes(evidence['review'],doc['editorial']['mode']) and policy.review_passes(portrait,doc['editorial']['mode'])
    for proof,field in ((evidence,'evidence_images'),(creative,'image_hashes')):
        for path,sha in proof[field].items():assert digest(path)==sha,'Review image changed'
    assert not creative['review']['issues'] and creative['review']['confidence']>=.85
    assert all(creative['review'][flag] for flag in ('distinct_core_event','distinct_concrete_arc','distinct_hook','distinct_payoff','central_event_observable','ending_observable','not_generic_climbing'))
    assert digest(item['preview'])==q['output_sha256'] and not q['errors']
    assert q['music']['usage_route']=='cleared' and q['music']['approval_status']=='approved'
    assert digest(q['music']['path'])==q['music']['approved_audio_sha256']
    assert digest(q['music']['license_evidence'])==q['music']['approved_evidence_sha256']
    decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',item['preview'],'-map','0:v:0','-map','0:a:0','-f','null','-'],capture_output=True,text=True)
    assert decoded.returncode==0 and not decoded.stderr.strip(),decoded.stderr
    cadence=[]
    for visual in q['visual_quality']['scenes']:
        actual=quality_checks.measure_cadence(item['preview'],visual['final_start'],min(3,visual['source_duration']),60,roi=visual['output_roi'])
        comparison=quality_checks.compare_cadence(visual['source_cadence'],actual)
        assert not comparison['error'],comparison
        cadence.append(comparison)
    if item['event_id']=='birthday':
        assert all(2383<=line['start']<line['end']<=2396 for line in doc['editorial']['dialogue'])
        assert 'pints' not in json.dumps(doc).lower(),'Metadata claims dialogue outside selected interval'
    out=dest/(item['event_id']+'_readability.jpg')
    subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss','8','-i',item['preview'],'-frames:v','1',str(out)],check=True)
    results.append({'event':item['event_id'],'preview':item['preview'],'source_intervals':[(c['start'],c['start']+c['duration']) for c in doc['clips']],
        'render_reused':True,'render_input_fingerprint':'passed','saved_evidence_and_originality_proofs':'passed; unchanged plan and image bytes',
        'full_decode':'passed','cadence':cadence,'final_editorial_score':portrait['score'],'music_license_bytes':'verified',
        'subtitle_readability_frame':str(out),'source_audio_present':q['source_audio_present']})
save(dest/'results.json',{'updated_utc':now(),'source_unchanged':True,'ai_requests':0,'results':results})
print(json.dumps(results,indent=2))
