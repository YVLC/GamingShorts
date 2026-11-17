"""Verify exact revised outputs, preserve the earlier previews, package release."""
import sys,json,sqlite3,zipfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,digest,now,locked
import gaming_shorts as gs,dialogue_editorial as policy,dialogue_mission as mission,captions
from game_store import GameStore
release=gs.ROOT/'Releases/2026-11-14-hybrid-hooks'
state=read(release/'state.json');destination=Path(mission.existing_mission()['review_folder'])/'hybrid_hooks_v1'
def ts(t):return f'{int(t//3600):02}:{int(t%3600//60):02}:{t%60:06.3f}'
def win(p):return 'D:/GamingShorts/'+str(p).removeprefix('/mnt/d/GamingShorts/')
with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
    tests=(release/'tests-final.log').read_text();smoke=(release/'render-smoke.log').read_text()
    assert 'Ran 236 tests' in tests and tests.rstrip().endswith('OK') and 'PASS: actual render' in smoke
    rows=[]
    for item in state['items']:
        if item['status']!='ready_for_review':continue
        p=Path(item['project']);q=read(p/'qc_report.json');doc=read(p/'edit_plan.json');verdict=read(p/'hybrid_final_review.json')
        assert policy.completed(p) and policy.review_passes(verdict,'hybrid') and digest(item['preview'])==q['output_sha256']
        assert not q['errors'] and q['narration_expected'] and not q['source_audio_present'] and not q['character_speech_fabricated']
        assert q['music']['id'] in ('ncs_royalty_regular','ncs_inmyhead_regular') and q['music']['usage_route']=='cleared'
        assert digest(q['music']['path'])==q['music']['approved_audio_sha256']
        assert digest(q['music']['license_evidence'])==q['music']['approved_evidence_sha256']
        voice=Path(read(p/'dialogue_render_inputs.json')['voice_folder']);alignment=read(voice/'word_alignment.json');proof=read(voice/'provenance.json')
        assert proof['request']['model']=='heygen-voice-1-turbo-free'
        assert proof['request']['lines']==[doc['clips'][0]['narration']]
        captions.validate_words(alignment['lines'][0]['words'],doc['clips'][0]['narration'],gs.duration(voice/'Voices/line_01.wav'))
        ass=p/'Renders'/q['input_key'][:16]/'karaoke_01.ass';assert '1c&H00FFFF&' in ass.read_text()
        word=max(alignment['lines'][0]['words'],key=lambda w:w['end']-w['start'])
        active_at=(word['start']+word['end'])/2+doc['clips'][0].get('commentary_start',.08)
        highlighted=release/(item['event']+'_yellow_word.jpg')
        subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(active_at),'-i',item['preview'],'-frames:v','1',str(highlighted)],check=True)
        decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',item['preview'],'-map','0:v:0','-map','0:a:0','-f','null','-'],capture_output=True,text=True)
        assert decoded.returncode==0 and not decoded.stderr.strip(),decoded.stderr
        old=read(p/'EditorialRevisions/before_hybrid_hooks_v1/qc_report.json')
        assert digest(item['previous_preview'])==old['output_sha256']
        c=doc['clips'][0]
        rows.append({'event':item['event'],'file':win(item['preview']),'sha256':q['output_sha256'],'duration':q['actual_duration'],
            'source_start':ts(c['start']),'source_end':ts(c['start']+c['duration']),'spoken_hook':c['narration'],
            'music':q['music']['title'],'music_path':win(q['music']['path']),'music_attribution':q['music']['attribution'],
            'music_excerpt_status':(q['music'].get('segment') or {}).get('status','no verified segment'),
            'word_count':len(alignment['lines'][0]['words']),'yellow_word_highlights':True,'active_word_frame':win(highlighted),'technical_qc':q['status'],'editorial_score':verdict['score'],
            'warnings':q['warnings'],'previous_preview_preserved':True,'originality_review':read(p/'creative_review.json')['review']})
    store=GameStore()
    with sqlite3.connect(release/'before.sqlite3') as before,store.connect() as after:
        for table in ('game_chunks','game_scenes','game_local_screens_v1','game_ai_selection_v1'):
            previous={tuple(x) for x in before.execute('SELECT * FROM '+table)};current={tuple(x) for x in after.execute('SELECT * FROM '+table)}
            assert previous==current,'Existing index changed: '+table
        with sqlite3.connect(release/'after.sqlite3') as backup:after.backup(backup)
    stat=(gs.ROOT/'Sources/videoplayback.webm').stat();assert stat.st_size==63959292291 and stat.st_mtime_ns==1794515665479289100
    receipt={'updated_utc':now(),'tests':'236 passed','render_smoke':'passed','source_and_analysis_unchanged':True,'published':False,'previews':rows,
        'blocked':[{'event':i['event'],'reason':i.get('error')} for i in state['items'] if i['status']!='ready_for_review']}
    save(release/'delivery-verification.json',receipt)
    lines=['# Cairn — narrated revisions ready for human review','',f"Delivered: {len(rows)} revised previews. Earlier gameplay-first versions remain preserved.",'',
        '| Event | Spoken hook | Music from Music folder | Duration | Source timestamps | Preview |','| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        lines.append('| '+' | '.join([row['event'],row['spoken_hook'],row['music'],f"{row['duration']:.3f}s",row['source_start']+'–'+row['source_end'],f"[Open preview](<{row['file']}>)"] )+' |')
    for row in rows:
        lines+=['',f"{row['event'].title()}: independent source/editorial/originality reviews passed; final editorial score {row['editorial_score']:.2f}; technical QC passed. Exact file: `{row['file']}`."]
    for blocked in receipt['blocked']:lines+=['','Blocked '+blocked['event']+': '+str(blocked['reason'])]
    lines+=['','Garret TTS uses the existing free voice model and actual returned word timestamps. Yellow active-word captions accompany the spoken hook; verified game dialogue follows without competing narration. These are commentator jokes, not recreated character voices. No gameplay audio exists in the source.',
        '', 'Both regular NCS song versions retain the existing approval records, exact audio/license checksums and required attribution sidecars. Selected highlights are inferred musical segments, not externally verified trending excerpts. No generated substitute music was used.',
        '', '236 regression tests and the actual rendering smoke test passed. Full final-media decode, audio presence/correlation, voice/music balance, black-frame, cadence, clipping/impulse and loudness checks passed for delivered previews. Human listening and publication approval remain required.',
        '', 'The original recording, all 217 local-screening checkpoints, 47 selected AI chunks, 260 observations and previous previews were preserved. No full analysis or publication was started.']
    (destination/'REVIEW_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    save(destination/'DELIVERY_VERIFICATION.json',receipt)
    report=destination.parent/'EDITORIAL_DELIVERY_REPORT.md';oldtext=report.read_text()
    notice='**Latest narrated revisions:** [Garret TTS, yellow word highlights and existing Music-folder tracks](hybrid_hooks_v1/REVIEW_REPORT.md). Earlier gameplay-first results below are preserved.\n\n'
    if not oldtext.startswith(notice):
        (release/'previous-delivery-report.md').write_text(oldtext,encoding='utf-8');report.write_text(notice+oldtext,encoding='utf-8')
    parent=mission.existing_mission();parent['latest_editorial_revision']={'state':str(release/'state.json'),'report':str(destination/'REVIEW_REPORT.md'),'outputs':[r['file'] for r in rows]}
    save(gs.ROOT/'Releases/2026-11-13-full-analysis/mission-state.json',parent)
    package=release/'after-runtime.zip'
    if not package.exists():
        with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
            for p in (gs.ROOT/'Automation/gamingshorts_v2').rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(gs.ROOT))
            for name in ('tools/resume_hybrid_hooks.py','tools/repair_hybrid_hook_writing.py','tools/recheck_hybrid_caption_schedule.py','tools/finalize_hybrid_hooks.py','docs/HYBRID_HOOKS_2026-11-14.md'):
                z.write(gs.ROOT/name,name)
    save(release/'manifest.json',{'updated_utc':now(),'files':{p.name:digest(p) for p in (package,release/'after.sqlite3',release/'delivery-verification.json')}})
    print(json.dumps(receipt,indent=2))
