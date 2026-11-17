"""Bounded integrity must not be promoted; local scores are not event labels."""
import tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import gaming_shorts as gs,game_index as index,local_index as local
from game_store import GameStore
from job_store import JobStore,stat_key

class LocalFirstTests(unittest.TestCase):
    def test_temporal_shortlist_is_bounded_and_spans_recording(self):
        rows=[{'ordinal':i,'screen':{'promising':True,'candidate_score':1000-i}} for i in range(217)]
        chosen=local.shortlist(rows,48,12)
        self.assertLessEqual(len(chosen),48);self.assertGreaterEqual(max(r['ordinal'] for r in chosen),190)
        self.assertEqual(local.shortlist(rows,0),[])
    def test_static_and_motion_are_only_local_hints(self):
        static=local.screen_metrics(np.zeros((120,36,64)),[])
        self.assertFalse(static['promising']);self.assertNotIn('spoiler',static)
        frames=np.random.default_rng(0).integers(0,255,(120,36,64))
        self.assertTrue(local.screen_metrics(frames,[2,40])['promising'])
    def test_partial_validation_reuses_receipts_and_never_publishes_global_pass(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            source=Path(temp)/'source.webm';source.write_bytes(b'fixture')
            proof={'source':str(source),'sha256':'fixture','fingerprint':stat_key(source.stat()),'probe':{'format':{'duration':'1800'},'streams':[{'codec_type':'video','avg_frame_rate':'60/1','width':3840,'height':2160}]}}
            store=GameStore();r=store.register('cairn','Cairn',proof);store.select('cairn');seen=[]
            def decode(*args,**kwargs):seen.append(kwargs['start']);return {'frames':100,'duration_seconds':kwargs['seconds']}
            with patch.object(JobStore,'admit_source',return_value=proof),patch.object(index,'validator_key',return_value='decoder'),patch.object(index,'decode_source',side_effect=decode):
                p=index.verify_integrity(r,needed_ranges=[(0,120)])
                self.assertEqual(p['integrity_scope'],'partial_checkpoint_coverage')
                index.verify_integrity(r,needed_ranges=[(0,234)]);self.assertEqual(seen,[0])
                with JobStore(Path(temp)).connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM decoded_sources').fetchone()[0],0)
                index.verify_integrity(r)
                self.assertEqual(len(seen),4)
                with JobStore(Path(temp)).connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM decoded_sources').fetchone()[0],1)
    def test_existing_index_cli_routes_to_bounded_local_pilot(self):
        import full_game
        from common import save
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            save(Path(temp)/'Releases/2026-11-13-full-analysis/progress.json',{'stage':'pilot_passed'})
            with patch.object(full_game,'config',return_value={'analysis_mode':'local_first'}),patch.object(full_game,'active_recording',return_value={}),patch.object(local,'execute') as execute:
                result=full_game.main(['index','--start','--pilot-only'])
                execute.assert_called_once_with(pilot_only=True)
                self.assertEqual(result['stage'],'pilot_passed')
