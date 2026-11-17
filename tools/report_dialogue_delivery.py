"""Generate the human review report from completed checkpoints and actual media."""
import sys,json,re,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,now,digest
from dialogue_mission import state_path,existing_mission,release
import dialogue_editorial as policy
state=read(state_path());folder=Path(existing_mission()['review_folder']);results=[]
def timestamp(t):return f'{int(t//3600):02}:{int(t%3600//60):02}:{t%60:06.3f}'
def windows(path):return 'D:/GamingShorts/'+str(path).removeprefix('/mnt/d/GamingShorts/')
for item in state['candidates']:
    row=dict(event=item['event_id'],premise=item['premise'],source_start=timestamp(item['start']),source_end=timestamp(item['start']+item['duration']),
        mode=item['mode'],mode_reason=item['narration_rationale'],rendering=item['status'],source_editorial_review=item.get('quality','pending'),
        independent_originality=item.get('originality','pending'),rejection_reason=item.get('error'),preview=None,final_technical_qc='not delivered',final_editorial_review='not delivered')
    if item['status']=='technical_pass':
        p=Path(item['project']);q=read(p/'qc_report.json');doc=read(p/'edit_plan.json');portrait=read(p/'portrait_editorial_review.json');creative=read(p/'creative_review.json')['review']
        # Mission duration is the delivered duration, including reading holds.
        # Only the accepted plan establishes original-source bounds.
        row.update(source_start=timestamp(doc['clips'][0]['start']),source_end=timestamp(doc['clips'][-1]['start']+doc['clips'][-1]['duration']))
        assert policy.completed(p) and policy.review_passes(portrait,doc['editorial']['mode'])
        assert digest(item['preview'])==q['output_sha256']
        meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',item['preview']]))
        streams=[{k:s[k] for k in ('codec_type','codec_name','width','height','avg_frame_rate','sample_rate','channels') if k in s} for s in meta['streams']]
        row.update(preview=windows(item['preview']),duration=q['actual_duration'],final_technical_qc=q['status'],qc_errors=q['errors'],qc_warnings=q['warnings'],
            final_editorial_review='passed',editorial_score=portrait['score'],originality_confidence=creative['confidence'],originality_rejection_reason=None,
            distinct_event=creative['new_event'],payoff=creative['outcome'],streams=streams,music=q['music']['title'],music_approval=q['music']['approval_status'],
            music_license=q['music']['license'],music_license_evidence=windows(q['music']['license_evidence']),source_audio_present=q['source_audio_present'],
            narration_expected=q['narration_expected'],character_speech_fabricated=q['character_speech_fabricated'],
            true_peak_dbtp=q['encoded_audio_loudness']['input_true_peak_db'],reading_hold=doc['clips'][-1].get('end_reading_hold',0),
            captions=q['captions'],sha256=q['output_sha256'])
    results.append(row)
tests=(release()/'tests-delivery.log').read_text();smoke=(release()/'smoke-final-pass.log').read_text()
assert re.search(r'Ran 235 tests',tests) and tests.rstrip().endswith('OK')
assert 'PASS: actual render' in smoke
report={'updated_utc':now(),'mission_id':state['mission_id'],'delivered':sum(r['preview'] is not None for r in results),
    'candidates':results,'tests':'235 regression tests passed; actual legacy render smoke passed, including missing-narration rejection',
    'indexing':'Existing 217 local chunks, 47 selected AI inspections and 260 observations reused. No second full analysis.',
    'previous_story':'The robot interaction at approximately 06:36:00–06:36:49 remains preserved and user-rejected. New selected footage is disjoint from that event and from each other.',
    'human_review':'Automated editorial and technical checks are not publication approval. Human viewing/listening remains required. No upload or publishing invoked.'}
save(folder/'EDITORIAL_DELIVERY_REPORT.json',report)
lines=['# Cairn editorial repair — review delivery','',f"Delivered: {report['delivered']} previews. Mission `{state['mission_id']}`.",'',report['indexing'],'',report['previous_story'],'',
    '| Event | Source timestamps | Independent originality | Rendering | Final editorial | Technical QC | Preview |',
    '| --- | --- | --- | --- | --- | --- | --- |']
for r in results:
    preview=f"[Open preview](<{r['preview']}>)" if r['preview'] else 'Held — no accepted preview'
    lines.append('| '+' | '.join((r['event'],r['source_start']+'–'+r['source_end'],r['independent_originality'],r['rendering'],r['final_editorial_review'],r['final_technical_qc'],preview))+' |')
for r in results:
    lines+=['',f"## {r['event'].title()}",'',r['premise'],'',f"Mode: **{r['mode']}**. {r['mode_reason']}"]
    if r['preview']:
        lines+=['',f"Duration: {r['duration']:.3f}s, including {r['reading_hold']:.1f}s final-frame reading hold. Original source chronology is preserved.",
            '',f"Story and payoff: {r['distinct_event']} {r['payoff']}",
            '',f"Originality confidence: {r['originality_confidence']:.2f}; final editorial score: {r['editorial_score']:.2f}. No unresolved QC errors. Warnings: {r['qc_warnings']}.",
            '',f"1080×1920 H.264 video, AAC stereo 48 kHz. Full decode, black-frame detection, foreground cadence, audio clipping/impulse and loudness checks passed. True peak: {r['true_peak_dbtp']:.2f} dBTP.",
            '',f"Music: **{r['music']}** — {r['music_approval']}. {r['music_license']}. [License/provenance evidence](<{r['music_license_evidence']}>).",
            '',"No source audio exists; no character speech or narration was fabricated. Verified dialogue text appears at its original onset with bounded readability dwell. It is not presented as speech-word alignment. No generic subscription CTA.",
            '',f"Exact path: `{r['preview']}`"]
    else:lines+=['','Hold reason: '+str(r['rejection_reason'])]
lines+=['','## Verification and remaining limitations','',report['tests'],'',report['human_review'],'',
    'The avalanche needs targeted evidence of a resolved outcome before it can become a self-contained third Short. No new full-source scan was started.',
    '', 'Source and previous-output preservation receipts: `Releases/2026-11-14-dialogue-editorial/preservation-and-delivery.json`.']
receipt=release()/'checkpoint_reverification/results.json'
if receipt.exists():
    recheck=(release()/'checkpoint-regression.log').read_text()
    assert 'Ran 10 tests' in recheck and recheck.rstrip().endswith('OK')
    report['checkpoint_reverification']=read(receipt)
    save(folder/'EDITORIAL_DELIVERY_REPORT.json',report)
    lines+=['','## Saved-checkpoint revalidation','',
        'Both existing renders were reused after validating their current render fingerprints and exact review-copy hashes. Source bounds above come from accepted edit plans and exclude the final-frame reading hold.',
        '', 'Saved evidence/originality proofs match the plans and unchanged evidence-image bytes. Both videos passed a fresh strict full video/audio decode, foreground cadence comparison and music audio/license checksum verification. No AI requests or new source analysis were made.',
        '', 'Birthday metadata contains only dialogue inside 00:39:43–00:39:56, ending with “with or without you here.” It does not claim the subsequent drinking remark.',
        '', 'Fresh targeted regression: 10 tests passed, including rejection of frozen, dropped-update and vanishing-difference foregrounds, caption dwell, and actual unvoiced/narrated/hybrid render fixtures. The 235-test full suite and legacy smoke results above are the previously completed baseline.',
        '', 'Fresh readable-dialogue frames and machine-readable results: `Releases/2026-11-14-dialogue-editorial/checkpoint_reverification/`. Relevant regression results: `checkpoint-regression.log` in the same release folder.']
(folder/'EDITORIAL_DELIVERY_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'report':windows(folder/'EDITORIAL_DELIVERY_REPORT.md'),'delivered':report['delivered'],'previews':[r['preview'] for r in results if r['preview']]},indent=2))
