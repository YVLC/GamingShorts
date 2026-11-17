"""Reuse authorization changes footage admission, not evidence or script quality."""
import unittest
from unittest.mock import patch
import common,story_policy,creative_history,game_plan

class ReuseTests(unittest.TestCase):
    def test_permission_is_bound_to_exact_recording(self):
        with patch.object(common,'config',return_value={'footage_reuse_sources':['authorized']}):
            self.assertTrue(story_policy.reuse_allowed('authorized'))
            self.assertFalse(story_policy.reuse_allowed('other'))
            self.assertFalse(story_policy.reuse_allowed(None))

    def test_strict_generated_schema_requires_new_music_field(self):
        def check(node):
            if isinstance(node,dict):
                if node.get('type')=='object':self.assertEqual(set(node['required']),set(node['properties']))
                for value in node.values():check(value)
            elif isinstance(node,list):
                for value in node:check(value)
        check(game_plan.PLAN)

    def test_reuse_review_does_not_require_different_physical_event(self):
        review={'review_mode':'authorized_footage_reuse','supported':True,'adds_new_value':True,
                'specific_hook':True,'hook_paid_off':True,'not_dialogue_dub':True,'not_rejected_story':True,
                'issues':[],'confidence':.95,'evidence':'Different commentary over verified reused scene.'}
        self.assertTrue(creative_history.review_passes(review))
        for field in ('supported','adds_new_value','not_dialogue_dub','not_rejected_story'):
            self.assertFalse(creative_history.review_passes(dict(review,**{field:False})))

if __name__=='__main__':unittest.main()
