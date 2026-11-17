"""Mode-aware expectations never treat intentionally absent speech as failed TTS."""
import json,tempfile,unittest,subprocess,shutil,copy
from pathlib import Path
from unittest.mock import patch,MagicMock
import common,gaming_shorts as gs,dialogue_editorial as policy

def plan(mode='gameplay-first',text=''):
    return {'editorial':{'policy':policy.VERSION,'mode':mode,'dialogue':[], 'premise':'A complete observed moment','hook':'Visual curiosity','payoff':'A real outcome',
        'added_value':'Context not supplied by the visible action','duration_reason':'A short complete event; no padded target','cta':False},
        'clips':[{'start':0,'duration':12,'scene_id':'scene','narration':text,'caption':'','evidence':'fixture event'}],
        'music':{'mood':'relaxed','instrumental_only':True}}

class DialoguePolicyTests(unittest.TestCase):
    def test_unvoiced_history_retains_hook_and_visible_dialogue(self):
        import creative_history
        doc=plan();doc['editorial']['dialogue']=[{'start':0,'end':2,'text':'A visible line.','confidence':.98,'evidence':'fixture frame'}]
        facts=creative_history.facts(doc)
        self.assertEqual(facts['hook'],'Visual curiosity');self.assertEqual(facts['source_dialogue'],doc['editorial']['dialogue'])
        self.assertEqual(facts['editorial_mode'],'gameplay-first')
        del doc['editorial']['policy'];doc['clips'][0]['narration']='Legacy spoken hook.'
        self.assertEqual(creative_history.facts(doc)['hook'],'Legacy spoken hook.')
    def test_low_motion_classification_boundary_is_not_a_frozen_video(self):
        from quality_checks import compare_cadence
        source={'active_windows':1,'active_updates_per_second':59.94,'mean_adjacent_difference':.09,'near_duplicate_fraction':.005}
        output={'active_windows':0,'updates_per_second_all':59.94,'mean_adjacent_difference':.092,'near_duplicate_fraction':0}
        self.assertEqual(compare_cadence(source,output)['status'],'pass')
        for updates,difference,duplicates in [(0,0,1),(20,.03,.66),(59.94,.001,0)]:
            bad=dict(output,updates_per_second_all=updates,mean_adjacent_difference=difference,near_duplicate_fraction=duplicates)
            self.assertEqual(compare_cadence(source,bad)['status'],'failed')
    def test_single_continuous_clip_and_no_cta_are_valid(self):
        self.assertEqual(len(policy.validate(plan(),{'duration':12})['clips']),1)

    def test_repeated_visible_dialogue_and_recap_rejected(self):
        dialogue=[{'text':'Robot, please turn back on.'}]
        self.assertTrue(policy.redundancy('Robot please turn back on.',dialogue))
        self.assertTrue(policy.redundancy('Now she says robot please.',dialogue))
        review={k:True for k in policy.FLAGS};review.update(score=.96,issues=[])
        self.assertTrue(policy.review_passes(review))
        review['nonredundant_narration']=False;self.assertFalse(policy.review_passes(review))
        review['nonredundant_narration']=True;review['narration_adds_value']=False
        self.assertFalse(policy.review_passes(review,'narrated'));self.assertFalse(policy.review_passes(review,'hybrid'))
        self.assertTrue(policy.review_passes(review,'gameplay-first'))
        review['issues']=['Unreadable source subtitle'];self.assertFalse(policy.review_passes(review,'gameplay-first'))

    def test_no_fake_speech_and_hybrid_is_brief(self):
        with self.assertRaisesRegex(ValueError,'must not synthesize'):policy.validate(plan(text='Pretend character speech'),{'duration':12})
        with self.assertRaisesRegex(ValueError,'requires commentary'):policy.validate(plan('narrated'),{'duration':12})
        policy.validate(plan('hybrid','Brief useful context.'),{'duration':12})
        with self.assertRaisesRegex(ValueError,'brief addition'):policy.validate(plan('hybrid',' '.join(['word']*40)),{'duration':12})

    def test_chronology_and_optional_cta_checks_remain(self):
        doc=plan('narrated','Useful context.')
        doc['clips'].append(dict(doc['clips'][0],start=5,cut_reason='downtime'))
        with self.assertRaisesRegex(ValueError,'Chronology'):policy.validate(doc,{'duration':30})
        with self.assertRaisesRegex(ValueError,'subscription'):policy.validate(plan('narrated','Subscribe for more.'),{'duration':12})

    def test_accessibility_dwell_never_anticipates_or_overlaps_next_line(self):
        lines=[dict(start=10,end=10.5,text='Haha, give me that, Rosie!',confidence=.98),dict(start=12,end=12.5,text='with or without you here.',confidence=.98)]
        before=copy.deepcopy(lines)
        windows=policy.presentation_windows(lines,10,4)
        self.assertEqual(lines,before)
        self.assertEqual(windows[0]['start'],0)
        self.assertGreaterEqual(windows[0]['end'],1.5)
        self.assertLessEqual(windows[0]['end'],windows[1]['start'])
        self.assertEqual(windows[1]['start'],2)
        self.assertGreaterEqual(windows[1]['end']-windows[1]['start'],1.5)

    def test_gameplay_first_never_calls_voice_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);common.save(p/'edit_plan.json',plan())
            with patch.object(policy,'guard'),patch.object(policy,'render',return_value=p/'final.mp4') as render,patch('voices.ensure') as voice:
                policy.run_project(p);voice.assert_not_called();render.assert_called_once_with(p,None)

    def test_actual_unvoiced_render_keeps_media_checks(self):
        if not shutil.which('ffmpeg'):self.skipTest('ffmpeg required')
        with tempfile.TemporaryDirectory() as tmp,patch.object(gs,'ROOT',Path(tmp)):
            root=Path(tmp);p=root/'fixture';p.mkdir();src=root/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-t','12','-c:v','libx264','-threads','1',str(src)],check=True)
            music=root/'fixture_music.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','15','-ac','2',str(music)],check=True)
            from job_store import stat_key
            r={'source':str(src),'sha256':common.digest(src),'fingerprint':stat_key(src.stat())}
            doc=plan();doc['clips'][0].update(framing='dialogue_portrait',focus_x=.43,end_reading_hold=1.5);common.save(p/'edit_plan.json',doc)
            common.save(p/'manifest.json',{'source':str(src),'source_sha256':r['sha256'],'duration':12})
            common.save(p/'dialogue_editorial_review.json',{'plan_key':common.key(doc),'review':'isolated renderer fixture'})
            track={'id':'fixture','path':str(music),'sha256':common.digest(music),'attribution':'Original synthetic test tone','instrumental':True,'beats':[i*.5 for i in range(32)],'bpm':120}
            common.save(p/'music_selection.json',track)
            cfg=dict(common.config(),root=str(root),width=360,height=640,fps=30,crf=26,x264_preset='ultrafast')
            with patch.object(policy,'guard',return_value=r),patch.object(policy,'verify_integrity') as integrity,patch.object(policy,'config',return_value=cfg),patch('music_library.select',return_value=track),patch('music_library.commit'):
                final=policy.render(p)
                integrity.assert_called_once();q=common.read(p/'qc_report.json')
                self.assertEqual(q['status'],'technical_pass');self.assertFalse(q['narration_expected'])
                self.assertFalse(q['source_audio_present']);self.assertFalse(q['character_speech_fabricated'])
                self.assertEqual(q['audio_windows'],[])
                self.assertAlmostEqual(q['actual_duration'],13.5,delta=.1)
                self.assertEqual(q['visual_quality']['scenes'][0]['source_duration'],12)
                self.assertEqual(q['visual_quality']['scenes'][0]['intentional_reading_hold'],1.5)
                self.assertEqual(q['visual_quality']['scenes'][0]['framing']['mode'],'dialogue_portrait')
                self.assertGreater(q['visual_quality']['scenes'][0]['framing']['output_roi'][3],.6)
                self.assertTrue(policy.completed(p))
                with self.assertRaisesRegex(ValueError,'verified speech'):self._missing_speech(p,doc,r)

    def _missing_speech(self,p,doc,r):
        doc=plan('narrated','A meaningful contextual observation.');common.save(p/'edit_plan.json',doc)
        return policy.render(p)

    def test_narrated_and_hybrid_real_render_paths_with_offline_voice_fixture(self):
        if not shutil.which('ffmpeg'):self.skipTest('ffmpeg required')
        import captions
        from job_store import stat_key
        with tempfile.TemporaryDirectory() as tmp,patch.object(gs,'ROOT',Path(tmp)):
            root=Path(tmp);src=root/'source.mp4';music=root/'bed.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30','-t','12','-c:v','libx264','-threads','1',str(src)],check=True)
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','15','-ac','2',str(music)],check=True)
            r={'source':str(src),'sha256':common.digest(src),'fingerprint':stat_key(src.stat())}
            track={'id':'fixture','path':str(music),'sha256':common.digest(music),'attribution':'Original synthetic fixture','instrumental':True,'beats':[i*.5 for i in range(32)],'bpm':120}
            cfg=dict(common.config(),root=str(root),width=360,height=640,fps=30,crf=28,x264_preset='ultrafast')
            for mode in ('narrated','hybrid'):
                with self.subTest(mode=mode):
                    p=root/mode;p.mkdir();doc=plan(mode,'Useful extra context.');voice=p/'VoiceVersions/fixture';(voice/'Voices').mkdir(parents=True)
                    wav=voice/'Voices/line_01.wav'
                    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=930:sample_rate=48000','-t','2','-ac','2',str(wav)],check=True)
                    common.save(voice/'provenance.json',{'files':{'line_01.wav':common.digest(wav)},'origin':'offline synthetic media fixture, not real speech generation'})
                    common.save(p/'edit_plan.json',doc);common.save(p/'manifest.json',{'source':str(src),'source_sha256':r['sha256'],'duration':12})
                    common.save(p/'dialogue_editorial_review.json',{'plan_key':common.key(doc),'review':'isolated renderer fixture'})
                    common.save(p/'music_selection.json',track)
                    alignment={'lines':[{'words':[{'word':word,'start':i*.5,'end':i*.5+.4} for i,word in enumerate(('Useful','extra','context.'))]}]}
                    with patch.object(policy,'guard',return_value=r),patch.object(policy,'verify_integrity'),patch.object(policy,'config',return_value=cfg),patch('music_library.select',return_value=track),patch('music_library.commit'),patch.object(captions,'_from_saved_heygen_words',return_value=alignment):
                        final=policy.render(p,voice);q=common.read(p/'qc_report.json')
                        self.assertEqual(q['status'],'technical_pass');self.assertTrue(q['narration_expected']);self.assertEqual(len(q['audio_windows']),1)
                        self.assertTrue(final.with_suffix('.srt').exists());self.assertTrue(policy.completed(p))
                        ass=next((p/'Renders').glob('*/karaoke_01.ass')).read_text()
                        self.assertIn('1c&H00FFFF&',ass)
                        if mode=='hybrid':
                            doc['clips'][0]['commentary_before_dialogue']=True
                            doc['editorial']['dialogue']=[dict(start=1,end=3,text='Visible source dialogue.',confidence=.99,evidence='fixture')]
                            common.save(p/'edit_plan.json',doc)
                            with self.assertRaisesRegex(ValueError,'overlaps game dialogue'):policy.render(p,voice)

if __name__=='__main__':unittest.main()
