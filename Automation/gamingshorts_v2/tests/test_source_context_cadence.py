import tempfile,unittest
from pathlib import Path
from common import save,key,digest
import source_context_cadence as context

class SourceContextCadenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.p=Path(self.temp.name)
        self.image=self.p/'inscription.png';self.image.write_bytes(b'readable original detail fixture')
        self.clip={'start':10,'duration':4}
        self.plan={'editorial':{'policy':'gaming-stories-v2','story_type':'lore','story_basis':'world_lore'},'clips':[self.clip]}
        self.recording={'sha256':'original'};self.result={'active_updates_per_second':15,'cadence_limited':True}
        self.review={k:True for k in ('supported','immediate_action','distinct_story','adds_value','hook_paid_off','not_dialogue_dub','cta_after_payoff','visual_story')};self.review['issues']=[]
        save(self.p/'evidence_review.json',{'plan_key':key(self.plan),'review':self.review})
        self.note={'purpose':'written_lore_with_ambient_context','plan_key':key(self.plan),'source_sha256':'original',
            'detail_images':{str(self.image):digest(self.image)},'entries':[dict(self.clip,result_key=key(self.result))]}
        save(self.p/'source_context_cadence.json',self.note)

    def test_only_exact_reviewed_lore_source_context_is_admitted(self):
        self.assertTrue(context.accepted(self.p,self.plan,self.clip,self.recording,self.result))
        self.assertFalse(context.accepted(self.p,self.plan,self.clip,{'sha256':'other'},self.result))
        self.assertFalse(context.accepted(self.p,self.plan,self.clip,self.recording,dict(self.result,active_updates_per_second=8)))
        self.image.write_bytes(b'changed detail')
        self.assertFalse(context.accepted(self.p,self.plan,self.clip,self.recording,self.result))

    def test_gameplay_and_rejected_source_reviews_cannot_use_context_admission(self):
        other=dict(self.plan,editorial=dict(self.plan['editorial'],story_type='beginner_tip',story_basis='gameplay_demonstration'))
        self.assertFalse(context.accepted(self.p,other,self.clip,self.recording,self.result))
        self.review['supported']=False
        save(self.p/'evidence_review.json',{'plan_key':key(self.plan),'review':self.review})
        self.assertFalse(context.accepted(self.p,self.plan,self.clip,self.recording,self.result))

if __name__=='__main__':unittest.main()
