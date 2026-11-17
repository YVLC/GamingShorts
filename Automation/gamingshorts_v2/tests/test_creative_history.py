"""New events require semantic evidence; music/synonym remixes are rejected."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import common,gaming_shorts as gs,creative_history as creative

class CreativeHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.patch=patch.object(gs,'ROOT',self.root);self.patch.start()
        self.p=self.root/'Projects/V2/new';self.p.mkdir(parents=True)
        self.plan={'editorial':{'premise':'A surprise chocolate drink at the shelter','structure':'cause_and_effect','payoff':'The quiet drink preparation makes survival tangible','beats':['Pick up chocolate','Drink','Pack supplies']},'clips':[{'start':i*5+30,'duration':5,'narration':x,'caption':'Evidence','evidence':x} for i,x in enumerate(['You can make hot chocolate here.','She handles a flask and tea bag.','The drink is ready. Subscribe for more.'])]}
        self.m={'source':'fixture.mp4','source_sha256':'source','duration':200}
        common.save(self.p/'manifest.json',self.m)
        self.old={'id':'old','project':'old','status':'validated','source':{'sha256':'source'},'facts':dict(creative.facts(self.plan),family=creative.family_key(self.plan)),'plan':self.plan}
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def new_plan(self):
        return {'editorial':{'premise':'A missed hold causes a fall caught by a rope','payoff':'The rope arrests the fall'},'clips':[{'start':100+i*5,'duration':5,'narration':x,'caption':'Evidence'} for i,x in enumerate(['That handhold just broke.','She drops before the rope catches.','The rope stops her fall. Subscribe for more.'])]}
    def test_music_caption_and_opening_do_not_make_new_family(self):
        changed=json.loads(json.dumps(self.plan));changed['music']={'track':'different'};changed['opening_action']={'start':5,'duration':1};changed['clips'][0]['caption']='Different'
        self.assertEqual(creative.family_key(changed),creative.family_key(self.plan))
        self.assertTrue(creative.compare(changed,self.m,[self.old])['issues'])
    def test_synonyms_dont_hide_reused_central_footage(self):
        changed=json.loads(json.dumps(self.plan));changed['editorial']={'premise':'A warm beverage helps endurance','payoff':'A restful preparation ritual'}
        for c in changed['clips']:c['narration']='A renamed observation with different words.'
        reasons=creative.compare(changed,self.m,[self.old])['issues'];self.assertTrue(any('footage overlap' in r['reason'] for r in reasons))
    def test_common_cta_is_not_a_repeated_payoff(self):
        self.assertFalse(creative.compare(self.new_plan(),self.m,[self.old])['issues'])
    def test_approved_footage_rejected_even_as_context(self):
        plan=self.new_plan();plan['clips'][0].update(start=30,duration=1,role='context')
        row=dict(self.old,status='approved')
        self.assertTrue(any('protected footage' in r['reason'] for r in creative.compare(plan,self.m,[row])['issues']))
    def test_limited_nonprotected_context_does_not_auto_reject_new_event(self):
        plan=self.new_plan();plan['clips'][0].update(start=30,duration=.5,role='context')
        self.assertFalse(creative.compare(plan,self.m,[self.old])['issues'])
    def test_ordered_visual_sequence_and_single_wall(self):
        frames=[{'dhash':x,'contrast':30,'luma':100} for x in ['0000000000000000','ffffffffffffffff','aaaaaaaaaaaaaaaa','5555555555555555']]
        self.assertTrue(creative.sequence_similarity(frames,frames)['repeated_sequence'])
        self.assertFalse(creative.sequence_similarity(frames[:1]*4,frames[:1]*4)['repeated_sequence'])
        self.assertFalse(creative.sequence_similarity(frames,list(reversed(frames)))['repeated_sequence'])
    def test_no_visual_evidence_means_no_model_or_automatic_approval(self):
        plan=self.new_plan()
        with patch.object(creative,'refresh'),patch.object(creative,'history',return_value=[]),patch.object(creative,'candidate_visuals',return_value=[]):
            with self.assertRaisesRegex(ValueError,'No candidate visual evidence'):creative.require_review(self.p,plan,invoke=True,images=[])
    def test_independent_semantic_review_rejects_paraphrased_same_event(self):
        plan=self.new_plan();image=self.root/'candidate.jpg';image.write_bytes(b'test evidence')
        result={k:True for k in ['distinct_core_event','distinct_concrete_arc','distinct_hook','distinct_payoff','central_event_observable','ending_observable','not_generic_climbing']}
        result.update(new_event='A same central event with synonyms',outcome='Same event conclusion',evidence='Fixture',matched_story_ids=[],issues=['Same core event'],confidence=.95)
        with patch.object(creative,'refresh'),patch.object(creative,'history',return_value=[]),patch.object(creative,'candidate_visuals',return_value=[]),patch('game_index.cached_ai',return_value=result):
            with self.assertRaisesRegex(ValueError,'semantic/visual story review failed'):creative.require_review(self.p,plan,invoke=True,images=[image])
    def test_semantic_receipt_binds_plan_history_and_images(self):
        plan=self.new_plan();image=self.root/'candidate.jpg';image.write_bytes(b'fixture')
        result={k:True for k in ['distinct_core_event','distinct_concrete_arc','distinct_hook','distinct_payoff','central_event_observable','ending_observable','not_generic_climbing']}
        result.update(new_event='Hold breaks; rope catches climber',outcome='Rope arrests fall',evidence='Fixture direct observation',matched_story_ids=[],issues=[],confidence=.95)
        with patch.object(creative,'refresh'),patch.object(creative,'history',return_value=[]),patch.object(creative,'candidate_visuals',return_value=[]),patch('game_index.cached_ai',return_value=result) as ai:
            creative.require_review(self.p,plan,invoke=True,images=[image]);creative.require_review(self.p,plan);self.assertEqual(ai.call_count,1)
            image.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Current semantic/visual'):creative.require_review(self.p,plan)
    def test_low_confidence_or_missing_outcome_never_passes(self):
        self.assertFalse(creative.review_passes({'confidence':.99}))
    def test_refresh_indexes_without_touching_original_source(self):
        common.save(self.p/'edit_plan.json',self.plan)
        with patch.object(creative,'visual_frame',side_effect=AssertionError('No historical output to sample')):
            summary=creative.refresh()
        self.assertEqual(len(summary['stories']),1)
        self.assertEqual(summary['stories'][0]['facts']['conclusion'],self.plan['editorial']['payoff'])
    def test_source_recording_cannot_be_hashed_or_decoded_as_historical_short(self):
        source=self.root/'Sources/original.webm';source.parent.mkdir();source.write_bytes(b'fixture original')
        common.save(self.p/'edit_plan.json',self.plan)
        common.save(self.p/'qc_report.json',{'status':'technical_pass','output':str(source)})
        with patch.object(creative,'decode_visual_cache',side_effect=AssertionError('Source scan attempted')):
            result=creative.refresh()
        self.assertTrue(any('source/proxy' in e for e in result['errors']))
