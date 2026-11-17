import ast
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
import ai_capacity as capacity
import game_index as index
import gaming_shorts as gs
import local_index
from common import digest

class CapacityTests(unittest.TestCase):
    def test_pilot_quota_does_not_stop_local_work(self):
        items=[{'ordinal':i,'start':i*114,'end':i*114+120,'screen':{'candidate_score':i}} for i in range(2)]
        calls=[]
        def prepare(*args):
            calls.append(args[-1]['ordinal'])
            if len(calls)==3:raise RuntimeError('local work reached')
            return args[-1]
        with patch.object(local_index,'GameStore'),patch.object(local_index,'locked',return_value=nullcontext()),patch.object(local_index,'setup',return_value=({'id':'recording','index_key':'key'},Path('/unused'))),patch.object(local_index,'chunks',return_value=items),patch.object(local_index,'prepare_chunk',side_effect=prepare),patch.object(local_index,'analyze_chunk',side_effect=capacity.Deferred('quota')),patch.object(local_index,'progress') as progress:
            with self.assertRaisesRegex(RuntimeError,'local work reached'):local_index.execute()
            self.assertEqual(calls,[0,1,0])
            self.assertIn('pilot_local_passed_ai_deferred',[c.args[2] for c in progress.call_args_list])

    def test_known_quota_not_uncertain_transport(self):
        self.assertTrue(capacity.quota_failure('You\u2019ve hit your usage limit.'))
        self.assertTrue(capacity.quota_failure("You've hit your usage limit"))
        self.assertFalse(capacity.quota_failure('connection reset or timed out'))

    def test_capacity_requires_positive_data(self):
        self.assertFalse(capacity.available({}))
        self.assertFalse(capacity.available({'rateLimits':{'primary':{'usedPercent':100}}}))
        self.assertTrue(capacity.available({'rateLimits':{'primary':{'usedPercent':22}}}))
        self.assertTrue(capacity.available({'rateLimits':{'primary':{'usedPercent':22},'credits':{'hasCredits':False}}}))
        same={'rateLimits':{'primary':{'usedPercent':99}}}
        self.assertFalse(capacity.recovered(same,same))
        self.assertTrue(capacity.recovered(same,{'rateLimits':{'primary':{'usedPercent':20}}}))

    def test_persisted_quota_avoids_generation_and_recovers_without_losing_attempt(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(gs,'ROOT',Path(tmp)):
            (Path(tmp)/'Database').mkdir()
            folder=Path(tmp)/'analysis'
            def exhausted(call,*args):
                (call/'events.candidate.json').write_text('')
                raise RuntimeError('usage_limit_reached')
            with patch.object(capacity,'capacity_read',return_value={'rateLimits':{'primary':{'usedPercent':100}}}),patch.object(index.editorial,'ai',side_effect=exhausted) as generate:
                with self.assertRaises(capacity.Deferred):index.cached_ai(folder,'prompt',{},[],'events')
                with self.assertRaises(capacity.Deferred):index.cached_ai(folder,'prompt',{},[],'events')
                self.assertEqual(generate.call_count,1)
            call=next(folder.glob('events_*'))
            self.assertTrue((call/'request.json').exists())
            with patch.object(capacity,'capacity_read',side_effect=RuntimeError('unavailable')) as probe:
                value=capacity.state();value['next_check']=0;capacity.persist(value)
                with self.assertRaises(capacity.Deferred):capacity.require_capacity()
                with self.assertRaises(capacity.Deferred):capacity.require_capacity()
                self.assertEqual(probe.call_count,1)
            value=capacity.state();value['next_check']=0;capacity.persist(value)
            with patch.object(capacity,'capacity_read',return_value={'rateLimits':{'primary':{'usedPercent':2}}}),patch.object(index.editorial,'ai',return_value={'scenes':[]}) as generate:
                result=index.cached_ai(folder,'prompt',{},[],'events')
                self.assertEqual(generate.call_count,1)
                self.assertEqual(result,{'scenes':[]})
            self.assertEqual(len(list((call/'CapacityAttempts').glob('*/request.json'))),1)
            self.assertEqual(len(list((call/'CapacityAttempts').glob('*/events.candidate.json'))),1)
            capacity.reject('quota')
            with patch.object(index.editorial,'ai',side_effect=AssertionError('no generation')):
                self.assertEqual(index.cached_ai(folder,'prompt',{},[],'events'),result)

    def test_uncertain_attempt_never_automatically_replayed(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(gs,'ROOT',Path(tmp)):
            (Path(tmp)/'Database').mkdir()
            with patch.object(index.editorial,'ai',side_effect=TimeoutError('timeout')) as generate:
                with self.assertRaises(TimeoutError):index.cached_ai(Path(tmp)/'analysis','p',{},[],'events')
                with self.assertRaisesRegex(RuntimeError,'Uncertain AI call'):index.cached_ai(Path(tmp)/'analysis','p',{},[],'events')
                self.assertEqual(generate.call_count,1)

    def test_scheduling_change_preserves_sampling_functions_and_identity(self):
        original=Path(__file__).resolve().parents[3]/'Releases/2026-11-13-ai-resilience/before/local_index.py'
        self.assertEqual(digest(original),local_index.SAMPLING_CONTROLLER_SHA256)
        def functions(path):
            text=path.read_text().replace('no semantic event, humor, outcome or spoiler assertion','no semantic event, humor, outcome or story assertion')
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        before=functions(original);after=functions(Path(local_index.__file__))
        # Semantic inspection intentionally changed to the new story brief;
        # numeric screening, chunk preparation and cached sampling stay fixed.
        for name in ('screen_metrics','local_screen','shortlist','prepare_chunk'):
            self.assertEqual(before[name],after[name],name)

if __name__=='__main__':unittest.main()
