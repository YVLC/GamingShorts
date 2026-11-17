"""Exact-version evidence, inferred highlights, timing and feedback safeguards."""
from pathlib import Path
import datetime as dt,json,tempfile,unittest,wave
from unittest.mock import patch
import numpy as np
import common,gaming_shorts as gs,music_segments as segments

class MusicSegmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.patch=patch.object(gs,'ROOT',self.root);self.patch.start()
        self.source=self.root/'song.wav';self.source.write_bytes(b'fixture song')
        self.sha=common.digest(self.source);self.version='original_regular'
        self.track={'id':'track','path':str(self.source),'sha256':self.sha,'approved_audio_sha256':self.sha,'version_id':self.version,'approval_status':'approved','usage_route':'cleared','mood':'suspense','energy':.6}
        self.plan={'clips':[{'duration':4,'narration':'A quiet opening.'},{'duration':4,'narration':'Danger, catch the fall!'},{'duration':4,'narration':'A rescue payoff.'}],'music':{'climax_at':6}}
        self.result={'audio_sha256':self.sha,'track_id':'track','version':self.version,'duration':160,'analysis_key':'fixture','segments':[self.segment('first',10,70,35),self.segment('second',80,145,100)]}
        segments.store_analysis(self.result)
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def segment(self,ident,start,end,climax):
        return {'id':ident,'track_id':'track','audio_sha256':self.sha,'version':self.version,'start':start,'end':end,'climax':climax,'status':'inferred','confidence':0.,'evidence':[],'verified_date':None,'mood':'suspense','energy':.6,'features':{'audio_confidence':.7,'popularity_confidence':0}}
    def verified(self):
        row=self.segment('ignored',80,140,100);today=dt.datetime.now(dt.timezone.utc).date().isoformat()
        row.update(confidence=.9,verified_date=today,verified_by='Isolated test reviewer',evidence=[{'url':'https://example.test/excerpts','scope':'excerpt_popularity','claim':'Isolated fixture confirms this exact excerpt and version is repeatedly used','version':self.version,'song_start':80,'song_end':140,'observed_date':today}]);return row
    def import_row(self,row):
        p=self.root/'verified.json';common.save(p,{'segments':[row]});return segments.import_verified(p)
    def test_verified_exact_excerpt_preferred_over_inferred(self):
        self.import_row(self.verified());chosen=segments.select_segment(self.root/'p',self.track,self.plan)
        self.assertEqual(chosen['status'],'verified');self.assertEqual(chosen['seek_start'],94)
        self.assertEqual(chosen['climax_alignment_error_seconds'],0)
        self.assertEqual(chosen['version'],self.version);self.assertEqual(chosen['popularity_confidence'],.9)
    def test_song_rank_and_loudness_are_not_excerpt_popularity(self):
        row=self.verified();row['evidence'][0]['scope']='song_popularity'
        with self.assertRaisesRegex(ValueError,'Excerpt-specific'):self.import_row(row)
        chosen=segments.select_segment(self.root/'p',self.track,self.plan)
        self.assertEqual(chosen['status'],'inferred');self.assertEqual(chosen['popularity_confidence'],0)
    def test_wrong_version_hash_and_unsupported_time_rejected(self):
        for field,value in [('version','sped_up'),('audio_sha256','different'),('end',200)]:
            row=self.verified();row[field]=value
            with self.assertRaises(ValueError):self.import_row(row)
        row=self.verified();row['evidence'][0]['song_start']=79
        with self.assertRaisesRegex(ValueError,'exact excerpt'):self.import_row(row)
    def test_platform_only_and_too_short_segments_are_not_eligible(self):
        self.assertEqual(segments.eligible_tracks([dict(self.track,usage_route='platform_only')],12),[])
        self.assertEqual(segments.eligible_tracks([self.track],100),[])
        self.assertIsNone(segments.select_segment(self.root/'p',dict(self.track,usage_route='platform_only'),self.plan))
    def test_offsets_stay_in_range_without_changing_story(self):
        before=common.key(self.plan);choice=segments.select_segment(self.root/'p',self.track,self.plan)
        self.assertGreater(choice['seek_start'],0);self.assertGreaterEqual(choice['seek_start'],choice['start']);self.assertLessEqual(choice['seek_end'],choice['end'])
        self.assertEqual(before,common.key(self.plan));self.assertEqual(choice,segments.select_segment(self.root/'p',self.track,self.plan))
    def test_feedback_improves_new_choices_not_pinned_rerenders(self):
        p=self.root/'p';first=segments.select_segment(p,self.track,self.plan)
        other='second' if first['id']=='first' else 'first'
        data={'results':[{'segment_id':other,'evidence_url':'https://example.test/review','observed_date':'2026-11-13','metrics':{'editor_rating':1,'views':100,'average_view_percentage':90}}]}
        path=self.root/'feedback.json';common.save(path,data);segments.import_feedback(path)
        self.assertEqual(first,segments.select_segment(p,self.track,self.plan))
        self.assertEqual(segments.select_segment(self.root/'new',self.track,self.plan)['id'],other)
    def test_technical_results_idempotent_and_not_fake_audience_data(self):
        selected={'segment':segments.select_segment(self.root/'p',self.track,self.plan)}
        segments.record_result('p','render',selected,{'kind':'technical_qc','status':'technical_pass'})
        segments.record_result('p','render',selected,{'kind':'technical_qc','status':'technical_pass'})
        with segments.editorial.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM music_segment_results_v1').fetchone()[0],1)
    def test_real_analysis_cached_and_never_claims_verified_trends(self):
        rate=8000;t=np.arange(rate*40)/rate
        # Deliberately loud ending cannot become verified popularity evidence.
        a=(.04+.12*(t>20))*np.sin(2*np.pi*220*t)*(0.5+0.5*(np.sin(2*np.pi*2*t)>0))
        with wave.open(str(self.source),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes((a*32767).astype('<i2').tobytes())
        sha=common.digest(self.source);track=dict(self.track,sha256=sha,approved_audio_sha256=sha)
        result=segments.analyze(track,self.root/'cache')
        self.assertGreater(len(result['segments']),0);self.assertTrue(all(s['status']=='inferred' and s['confidence']==0 for s in result['segments']))
        with patch.object(segments.subprocess,'run',side_effect=AssertionError('Unnecessary audio reanalysis')):
            self.assertEqual(result,segments.analyze(track,self.root/'cache'))
