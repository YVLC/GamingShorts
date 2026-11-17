import tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from common import save,key,digest,config
import quality_reference,visual_preflight,event_discovery

class ApprovedQualityTests(unittest.TestCase):
    def test_reference_needs_approval_and_unchanged_plan_and_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);out=p/'approved.mp4';out.write_bytes(b'approved bytes');plan={'clips':[]}
            row={'plan':plan,'plan_key':key(plan),'output':str(out),'output_sha256':digest(out),
                'approval':{'output_sha256':digest(out),'approved_utc':'2026-11-15','input_key':'reviewed'}}
            ref=p/'reference.json';save(ref,{'schema':1,'approval_basis':'explicit user acceptance','examples':[row]})
            self.assertEqual(len(quality_reference.examples(ref)),1)
            out.write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError,'changed'):quality_reference.examples(ref)
            row['approval']={};save(ref,{'schema':1,'approval_basis':'technical pass is insufficient','examples':[row]})
            with self.assertRaisesRegex(ValueError,'approval'):quality_reference.examples(ref)

    def test_conversations_are_demoted_even_if_catalog_scores_them_highly(self):
        conversation={'description':'Marco speaks in a subtitled conversation','score':.99}
        discovery={'description':'Ruins and a named artifact beside a cliff','score':.6}
        self.assertLess(event_discovery.visual_priority(discovery),event_discovery.visual_priority(conversation))

    def test_real_preview_cache_changes_with_caption_layout_and_rejection_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);source=p/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=navy:s=1280x720:r=10:d=2','-c:v','libx264','-threads','1',str(source)],check=True)
            save(p/'manifest.json',{'source':str(source),'source_sha256':digest(source),'duration':2})
            c={'start':0,'duration':2,'narration':'Repeat for the other damaged fingers.','framing':'tracked_cover','tracking':[{'at':0,'x':.5}],'caption_y':.86}
            doc={'editorial':{'policy':'gaming-stories-v2'},'clips':[c]}
            cfg=dict(config(),width=180,height=320)
            good={k:True for k in ('fullscreen','subject_visible','captions_clear','sampled_frames_clear')};good['issues']=[]
            with patch.object(visual_preflight,'config',return_value=cfg),patch.object(quality_reference,'approved_current',return_value=False),patch('game_index.cached_ai',return_value=good) as ai:
                receipt=visual_preflight.require_review(p,doc)
                self.assertEqual(len(receipt['image_hashes']),3)
                # Real caption pixels must wrap inside the frame, including a
                # wide phrase that the old drawtext approximation clipped.
                import numpy as np
                frame=next(iter(receipt['image_hashes']))
                raw=subprocess.run(['ffmpeg','-v','error','-i',frame,'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],capture_output=True,check=True).stdout
                pixels=np.frombuffer(raw,np.uint8).reshape(320,180,3)
                text=(pixels[:,:,0]>190)&(pixels[:,:,1]>190)
                self.assertGreater(text.sum(),15)
                x=np.where(text)[1];self.assertGreater(x.min(),5);self.assertLess(x.max(),174)
                visual_preflight.require_review(p,doc,invoke=False);self.assertEqual(ai.call_count,1)
                c['caption_y']=.76
                with self.assertRaisesRegex(ValueError,'required before narration'):visual_preflight.require_review(p,doc,invoke=False)
                ai.return_value=dict(good,captions_clear=False,issues=['Caption overlaps Take button'])
                with self.assertRaisesRegex(ValueError,'rejected before narration'):visual_preflight.require_review(p,doc)

if __name__=='__main__':unittest.main()
