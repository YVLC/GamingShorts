"""License, rotation, recovery, trend and real mixing regression checks."""
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
import numpy as np
import common,editorial,gaming_shorts as gs,music_library as music,music_mix

class MusicIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.p=self.root/'project';self.p.mkdir()
        self.plan={'clips':[{'duration':4,'narration':'Danger on a narrow hold'}]*3}
        common.save(self.p/'edit_plan.json',self.plan)
        self.tracks=[self.track(i) for i in range(25)]
        self.cat=self.root/'catalog.json';common.save(self.cat,{'tracks':self.tracks})
        self.cfg=dict(common.config(),music_catalog=str(self.cat),music_rotation=True,music_strategy="library")
        self.patches=[patch.object(gs,'ROOT',self.root),patch.object(music,'config',return_value=self.cfg)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def track(self,n):
        audio=self.root/f'{n}.wav';audio.write_bytes(str(n).encode());proof=self.root/f'{n}.txt';proof.write_text('Isolated test rights evidence')
        return {'id':str(n),'title':f'Track {n}','artist':'Fixture','source':'fixture','genre':'electronic','mood':'suspense' if n%2 else 'relaxed','energy':.55,'bpm':90,'license':'test only','attribution':'Fixture credit','attribution_required':True,'license_evidence':str(proof),'source_url':'https://example.test/license','path':str(audio),'approval_status':'approved','usage_route':'cleared','permitted_use':'youtube_ugc','approved_audio_sha256':common.digest(audio),'approved_evidence_sha256':common.digest(proof)}
    def test_twenty_five_tracks_and_mood(self):
        self.assertEqual(len(music.catalog()),25);self.assertEqual(music.select(self.p)['mood'],'suspense')

    def test_story_music_prefers_instrumental_but_allows_explicit_vocals(self):
        self.cfg['music_strategy']='story_music'
        self.plan['editorial']={'policy':'gaming-stories-v1'}
        self.plan['music']={'mood':'suspense','allow_vocals':True};common.save(self.p/'edit_plan.json',self.plan)
        self.tracks[1]['instrumental']=True
        for track in self.tracks:
            if track['id']!='1':track['instrumental']=False
        common.save(self.cat,{'tracks':self.tracks})
        with patch('music_segments.select_segment',return_value=None):
            self.assertEqual(music.select(self.p)['id'],'1')
            for track in self.tracks:track['instrumental']=False
            common.save(self.cat,{'tracks':self.tracks})
            self.assertIsNotNone(music.select(self.p)['path'])
            self.plan['music']['allow_vocals']=False;common.save(self.p/'edit_plan.json',self.plan)
            with self.assertRaisesRegex(ValueError,'No cleared music'):music.select(self.p)

    def test_story_mood_is_not_sacrificed_for_rotation(self):
        self.cfg['music_strategy']='story_music';self.plan['editorial']={'policy':'gaming-stories-v1'}
        self.plan['music']={'mood':'suspense','allow_vocals':False}
        for track in self.tracks:track['instrumental']=True
        self.tracks=[self.tracks[0],self.tracks[1]]
        common.save(self.cat,{'tracks':self.tracks});common.save(self.p/'edit_plan.json',self.plan)
        with patch('music_segments.select_segment',return_value=None):
            first=music.select(self.p)
            other=self.root/'second';other.mkdir();common.save(other/'edit_plan.json',self.plan)
            second=music.select(other)
            self.assertEqual(first['mood'],'suspense');self.assertEqual(second['id'],first['id'])
    def test_requested_local_songs_never_generate_a_substitute(self):
        self.cfg['music_strategy']='segments_then_new_original'
        self.plan['music']={'track_ids':['1']};common.save(self.p/'edit_plan.json',self.plan)
        with patch('music_composer.compose') as compose,patch('music_segments.select_segment',return_value=None):
            chosen=music.select(self.p)
            self.assertEqual(chosen['id'],'1');compose.assert_not_called()
            self.tracks[1]['usage_route']='platform_only';common.save(self.cat,{'tracks':self.tracks})
            with self.assertRaisesRegex(ValueError,'not cleared'):music.select(self.p)
            compose.assert_not_called()
    def test_reject_tampered_audio_and_rights(self):
        Path(self.tracks[0]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):music.catalog()
        result=music.select(self.p);self.assertIsNone(result['path']);self.assertIn('validation failed',result['reason'])
    def test_unapproved_and_platform_only_never_mixed(self):
        for t in self.tracks:t['usage_route']='platform_only'
        common.save(self.cat,{'tracks':self.tracks});self.assertIsNone(music.select(self.p)['path'])
        for t in self.tracks:t['usage_route']='cleared';t['approval_status']='pending'
        common.save(self.cat,{'tracks':self.tracks});self.assertEqual(music.catalog(),[])
    def test_required_credit_and_expired_license(self):
        self.tracks[0]['attribution']='';common.save(self.cat,{'tracks':self.tracks})
        with self.assertRaisesRegex(ValueError,'attribution'):music.catalog()
        self.tracks[0]['attribution']='credit';self.tracks[0]['approval_expires']='2020-01-01';common.save(self.cat,{'tracks':self.tracks})
        with self.assertRaisesRegex(ValueError,'expired'):music.catalog()
    def test_no_consecutive_tracks_pin_and_sidecar_recovery(self):
        a=music.select(self.p);(self.p/'music_selection.json').unlink();self.assertEqual(a,music.select(self.p))
        other=self.root/'other';other.mkdir();common.save(other/'edit_plan.json',self.plan)
        b=music.select(other);self.assertNotEqual(a['sha256'],b['sha256'])
    def test_failed_jobs_dont_count_and_rerenders_count_once(self):
        selected=music.select(self.p);self.assertTrue(all(t['usage']['uses']==0 for t in music.inventory()))
        output=self.root/'test.mp4';output.write_bytes(b'fixture successful output')
        music.commit(self.p,selected,output,'render-1',{'ducking':True});music.commit(self.p,selected,output,'render-2',{'ducking':False})
        self.assertEqual(sum(t['usage']['uses'] for t in music.inventory()),1)
        with editorial.connect() as db:self.assertIn('ducking',db.execute('SELECT audio_config_json FROM music_assignments_v2').fetchone()[0])
    def test_sole_track_and_missing_catalog_safe_silence(self):
        common.save(self.cat,{'tracks':self.tracks[:1]});music.select(self.p)
        other=self.root/'other';other.mkdir();common.save(other/'edit_plan.json',self.plan)
        self.assertIsNone(music.select(other)['path']);self.cat.unlink();self.assertIsNone(music.select(self.p)['path'])
    def test_bad_beat_metadata(self):
        self.tracks[0]['beats']=[2,1];common.save(self.cat,{'tracks':self.tracks})
        with self.assertRaisesRegex(ValueError,'beat'):music.catalog()
    def test_trend_import_atomic_and_separate(self):
        f=self.root/'trends.json';row={'id':'test','title':'Song','artist':'Artist','platform':'YouTube','discovery_date':'2026-11-13','popularity_evidence':'Fixture chart','permitted_usage_route':'platform_only','source_url':'https://example.test/chart'}
        common.save(f,{'trends':[row]});self.assertEqual(music.import_trends(f),1);self.assertEqual(music.trends()[0]['permitted_usage_route'],'platform_only')
        common.save(f,{'trends':[row,dict(row,id='bad',permitted_usage_route='illegal')]})
        with self.assertRaises(ValueError):music.import_trends(f)
        self.assertEqual(len(music.trends()),1)
    def test_phase_alignment_never_changes_shots(self):
        cuts=[3.,7.,11.];copy=list(cuts);report=music_mix.beat_alignment({'bpm':120,'beats':[i*.5 for i in range(40)]},cuts)
        self.assertEqual(cuts,copy);self.assertLessEqual(report['mean_cut_to_beat_seconds'],.001)
    def test_real_ducking_silence_fallback_and_master_limits(self):
        import audio_pipeline
        from common import run
        rate=48000;t=np.arange(8*rate)/rate
        voice=.12*np.sin(2*np.pi*220*t)*((t>2)&(t<5))
        # Smooth actual signal edges so this fixture tests ducking, not inserted impulses.
        voice*=np.minimum(1,np.maximum(0,(t-2)/.02))*np.minimum(1,np.maximum(0,(5-t)/.02))
        speech=self.root/'speech.wav';audio_pipeline.export_segment(voice,speech)
        bed=self.root/'bed.wav';audio_pipeline.export_segment(.08*np.sin(2*np.pi*400*t),bed)
        cfg=dict(self.cfg,music_lufs=-27,audio_mix={'threshold':.005,'ratio':10})
        out=self.root/'mix';out.mkdir()
        mix,ref,ducked,report=music_mix.mix(speech,{'path':str(bed)},8,out,cfg,run)
        data=audio_pipeline.read_audio(out/'music.wav');raw=audio_pipeline.read_audio(out/'music_level.wav')
        lo,hi=3*rate,4*rate;self.assertLess(audio_pipeline.level(data[lo:hi]),audio_pipeline.level(raw[lo:hi])-2)
        self.assertLessEqual(report['measured_true_peak_db'],-1.3)
        self.assertAlmostEqual(len(audio_pipeline.read_audio(mix))/rate,8,places=2)
        out2=self.root/'silent-mix';out2.mkdir();result=music_mix.mix(speech,music.silence('no approved track'),8,out2,cfg,run)
        self.assertFalse(result[-1]['music_present']);self.assertEqual(np.count_nonzero(audio_pipeline.read_audio(out2/'music.wav')),0)
    def test_beat_detector_reuses_content_checked_cache(self):
        import audio_pipeline
        rate=48000;t=np.arange(rate*4)/rate
        audio=self.root/'beats.wav';audio_pipeline.export_segment(.1*np.sin(2*np.pi*330*t)*(np.sin(2*np.pi*2*t)>0),audio)
        cache=self.root/'beat-cache.json';first=music_mix.detect_beats(audio,cache)
        with patch.object(music_mix.subprocess,'run',side_effect=AssertionError('Unexpected reanalysis')):
            self.assertEqual(first,music_mix.detect_beats(audio,cache))
    def test_actual_gameplay_audio_is_preserved_and_silent_source_not_fabricated(self):
        import subprocess,audio_pipeline
        source=self.root/'game.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=96x64:r=10:d=2','-f','lavfi','-i','sine=f=440:d=2','-c:v','libx264','-c:a','aac','-shortest',str(source)],check=True,capture_output=True)
        out=self.root/'game-audio';out.mkdir();sources=[{'path':source,'start':0,'duration':2}]
        result=music_mix.gameplay_stem(sources,out,2,self.cfg,common.run,gs.probe)
        self.assertGreater(float(np.max(np.abs(audio_pipeline.read_audio(result)))),0)
        self.assertIsNone(music_mix.gameplay_stem(sources,out,2,self.cfg,common.run,lambda _: {'streams':[{'codec_type':'video'}]}))
    def test_invalid_mix_levels_and_unknown_settings_rejected(self):
        for bad in ({'ratio':100},{'unknown':True},{'target_lufs':float('nan')}):
            with self.assertRaises(ValueError):music_mix.settings({'audio_mix':bad})
    def test_music_or_caption_rerender_and_failure_keep_one_successful_short(self):
        selected=music.select(self.p);output=self.root/'success.mp4';output.write_bytes(b'final')
        music.commit(self.p,selected,output,'first',{})
        self.plan['clips'][0]['caption']='Changed caption'
        common.save(self.p/'edit_plan.json',self.plan);changed=music.select(self.p)
        # A reserved/failed new version neither increments nor erases the last success.
        self.assertEqual(sum(t['usage']['uses'] for t in music.inventory()),1)
        music.commit(self.p,changed,output,'second',{})
        self.assertEqual(sum(t['usage']['uses'] for t in music.inventory()),1)
        with editorial.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM music_render_events_v2').fetchone()[0],2)
    def test_fresh_composition_reused_only_for_same_short_and_tampering_rejected(self):
        import music_composer
        a=music_composer.compose(self.p,self.plan,{'mood':'suspense','energy':.5},self.root)
        b=music_composer.compose(self.p,self.plan,{'mood':'suspense','energy':.5},self.root)
        self.assertEqual(a,b)
        other=music_composer.compose(self.root/'second',self.plan,{'mood':'suspense','energy':.5},self.root)
        self.assertNotEqual(a['sha256'],other['sha256'])
        Path(a['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):music_composer.compose(self.p,self.plan,{'mood':'suspense','energy':.5},self.root)
    def test_trending_preference_and_new_original_fallback(self):
        from datetime import datetime,timezone
        self.cfg['music_strategy']='trending_then_new_original'
        f=self.root/'trends.json';row={'id':'trend','title':'Track','artist':'Fixture','platform':'YouTube','discovery_date':datetime.now(timezone.utc).date().isoformat(),'popularity_evidence':'Isolated test chart','permitted_usage_route':'cleared','library_track_id':'1','source_url':'https://example.test/chart'}
        common.save(f,{'trends':[row]});music.import_trends(f)
        self.assertEqual(music.select(self.p)['id'],'1')
        row['permitted_usage_route']='platform_only';common.save(f,{'trends':[row]});music.import_trends(f)
        fresh=music.select(self.p);self.assertEqual(fresh['source'],'generated_per_short')
        self.assertEqual(fresh,music.select(self.p))
    def test_required_music_credits_in_manual_metadata_and_publication_check(self):
        import upload_metadata,publication
        music={'path':'fixture.wav','attribution_required':True,'attribution':'Artist - Track\nRequired source credit'}
        common.save(self.p/'qc_report.json',{'music':music})
        result=upload_metadata.music_metadata(self.p,{'game':'Fixture'})
        self.assertIn(music['attribution'],result['description'])
        publication.validate_music_credit({'snippet':{'description':result['description']}},music)
        with self.assertRaisesRegex(ValueError,'attribution'):publication.validate_music_credit({'snippet':{'description':'Missing credit'}},music)
    def test_failed_qa_cannot_commit_music_usage(self):
        selected=music.select(self.p);output=self.root/'failed.mp4';output.write_bytes(b'bad final')
        with self.assertRaisesRegex(ValueError,'technical QC'):
            music.commit(self.p,selected,output,'failed',{},performance={'status':'failed','output':str(output)})
        self.assertEqual(sum(t['usage']['uses'] for t in music.inventory()),0)
