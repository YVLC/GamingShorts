"""Behavioral contract for narrative Shorts and complete feature retirement."""
import copy,importlib.util,tempfile,unittest,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import story_policy as policy,game_plan,game_index,game_store,common,gaming_shorts as gs

def story():
    doc={'editorial':{'policy':policy.VERSION,'story_type':'lore','story_basis':'world_lore','viewer_value':'Explain an environmental clue',
            'hook_promise':'Who was here before the climb?','payoff_evidence':'Visible ruins and a named climbing artifact',
            'narration_added_value':'Connect environmental traces to the mountain history',
            'claims':[{'claim':'The mountain contains worked stone structures','evidence':'Visible masonry and cliffside architecture','basis':'footage','reference_id':''}]},
            'clips':[{'narration':'Who came here before this climb?'},{'narration':'The ruins and tools are clues to the mountain past.'},{'narration':'Exploring means looking at what remains. Subscribe for more.'}]}
    for c in doc['clips']:c.update(framing='tracked_cover')
    return doc

class StoryPolicyTests(unittest.TestCase):
    def test_all_requested_story_types_are_supported(self):
        for angle in policy.ANGLES:
            doc=story();doc['editorial']['story_type']=angle
            if angle=='gaming_trend':continue
            policy.validate(doc)

    def test_missing_claim_payoff_or_closing_cta_is_rejected(self):
        for field in ('claims','viewer_value','hook_promise','payoff_evidence','narration_added_value'):
            doc=story();doc['editorial'].pop(field)
            with self.assertRaises(ValueError):policy.validate(doc)
        doc=story();doc['clips'][-1]['narration']='No ending'
        with self.assertRaisesRegex(ValueError,'Subscribe'):policy.validate(doc)

    def test_direct_dialogue_redub_is_rejected(self):
        doc=story();doc['editorial']['dialogue']=[{'text':' '.join(c['narration'] for c in doc['clips']).removesuffix('Subscribe for more.')}]
        with self.assertRaisesRegex(ValueError,'Subtitle reading'):policy.validate(doc)

    def test_conversation_foundation_and_blur_filler_are_rejected(self):
        doc=story();doc['editorial']['story_basis']='conversation'
        with self.assertRaisesRegex(ValueError,'visual story foundation'):policy.validate(doc)
        doc=story();doc['clips'][0]['framing']='blur_contain'
        with self.assertRaisesRegex(ValueError,'full-screen'):policy.validate(doc)

    def test_research_claim_requires_real_supplied_reference(self):
        doc=story();doc['editorial']['claims'][0].update(basis='reference',reference_id='source')
        with self.assertRaisesRegex(ValueError,'Unknown research'):policy.validate(doc)
        policy.validate(doc,[{'id':'source'}])

    def test_trending_claim_requires_recent_platform_evidence(self):
        doc=story();doc['editorial']['story_type']='gaming_trend'
        doc['editorial']['claims'][0].update(basis='reference',reference_id='source')
        today=datetime.now(timezone.utc).date()
        with self.assertRaisesRegex(ValueError,'recent'):policy.validate(doc,[{'id':'source','platform':'YouTube','checked_date':str(today-timedelta(days=31))}])
        policy.validate(doc,[{'id':'source','platform':'YouTube','checked_date':str(today)}])

    def test_independent_review_cannot_accept_a_dub_or_missing_payoff(self):
        review={k:True for k in ('supported','immediate_action','distinct_story','adds_value','hook_paid_off','not_dialogue_dub','cta_after_payoff','visual_story')};review['issues']=[]
        self.assertTrue(policy.review_passes(review))
        for flag in ('adds_value','hook_paid_off','not_dialogue_dub','cta_after_payoff'):
            self.assertFalse(policy.review_passes(dict(review,**{flag:False})))

    def test_new_projects_use_story_planner_and_yellow_captions(self):
        cfg=common.config()
        self.assertEqual(cfg['editorial_policy'],policy.VERSION)
        self.assertEqual(cfg['caption_mode'],'karaoke')
        self.assertEqual(cfg['voice_model'],'heygen-voice-1-turbo-free')
        self.assertFalse(any('spoiler' in k for k in cfg))
        self.assertIsNone(importlib.util.find_spec('spoilers'))
        self.assertNotIn('spoiler',game_index.SCENE['properties'])
        self.assertNotIn('spoilers',game_plan.PLAN['properties']['editorial']['properties'])

    def test_retired_database_column_migrates_without_losing_scene_evidence(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(gs,'ROOT',Path(tmp)):
            path=Path(tmp)/'Database/editorial_v2.sqlite3';path.parent.mkdir()
            legacy=game_store.SCHEMA.replace(' evidence TEXT NOT NULL, tags_json TEXT NOT NULL,',' spoiler TEXT NOT NULL, evidence TEXT NOT NULL, tags_json TEXT NOT NULL,')
            with sqlite3.connect(path) as db:
                db.executescript(legacy)
                db.execute('INSERT INTO game_scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('s','r','i',0,1,4,'A secret','discovery',.99,'major','Visible hidden path','[]','["1"]',.9,None))
            store=game_store.GameStore()
            with store.connect() as db:
                row=dict(db.execute('SELECT * FROM game_scenes').fetchone())
                self.assertNotIn('spoiler',row);self.assertEqual(row['evidence'],'Visible hidden path')
            self.assertTrue((Path(tmp)/'Releases/2026-11-14-gaming-stories/legacy-database.sqlite3').exists())

if __name__=='__main__':unittest.main()
