import unittest
from common import save
import test_full_game as full_fixture

class SupportingContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture=full_fixture.FullGameTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        f=self.fixture;self.anchor=f.scene('anchor',7200,7220,category='mechanic')
        self.support=f.scene('context',7180,7190,category='discovery',score=.48)
        self.p=f.root/'project'
        self.context={'source_sha256':f.r['sha256'],'anchor_scene_id':'anchor','supporting_scene_ids':['context'],
            'purpose':'Diagram sets up the nearby lighting interaction.'}
        save(self.p/'scene_context.json',self.context)

    def test_support_requires_exact_source_anchor_and_close_evidence(self):
        store=self.fixture.store
        self.assertFalse(store.eligible(self.support))
        self.assertTrue(store.eligible(self.support,project=self.p))
        for changes in ({'confidence':.8},{'rejected':'explicit rejection'},{'start':7000}):
            self.assertFalse(store.eligible(dict(self.support,**changes),project=self.p))
        save(self.p/'scene_context.json',dict(self.context,source_sha256='other source'))
        self.assertFalse(store.eligible(self.support,project=self.p))

    def test_context_cannot_become_most_of_the_story(self):
        plan={'clips':[{'scene_id':'anchor','start':7200,'duration':4},{'scene_id':'context','start':7180,'duration':10}]}
        with self.assertRaisesRegex(ValueError,'central demonstrated event'):
            self.fixture.store.reserve(self.p,plan,[self.anchor,self.support])

if __name__=='__main__':unittest.main()
