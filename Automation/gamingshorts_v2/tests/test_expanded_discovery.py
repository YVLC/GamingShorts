import json,tempfile,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch,MagicMock
import gaming_shorts as gs,game_plan,shared_index,event_discovery
from common import save,read,digest,config
from game_store import GameStore

class ExpandedDiscoveryTests(unittest.TestCase):
    def test_physical_event_ranking_is_only_selection_not_approval(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            r={'sha256':'source','index_key':'fixture'}
            groups=[{'id':'dialogue','suitable':True,'confidence':.99,'scene_ids':['a']},{'id':'physical','suitable':True,'confidence':.85,'scene_ids':['b']}]
            save(event_discovery.folder(r)/'catalog.json',{'index_key':'fixture','events':groups})
            scenes=[{'id':'a','start':0,'end':35,'score':.99,'category':'discovery'},{'id':'b','start':100,'end':135,'score':.8,'category':'failure'}]
            fake=MagicMock();fake.eligible.return_value=True;fake.connect.return_value.__enter__.return_value.execute.return_value=[]
            with patch.object(event_discovery,'GameStore',return_value=fake):ordered=event_discovery.prioritized(scenes,r)
            self.assertEqual(ordered[0]['id'],'a');self.assertNotIn('independent_creative_review',ordered[0])
    def test_held_event_families_do_not_starve_the_unused_pool(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            r={'sha256':'source','index_key':'fixture'}
            groups=[{'id':str(i),'suitable':True,'confidence':.99-i*.01,'scene_ids':[str(i)]} for i in range(5)]
            save(event_discovery.folder(r)/'catalog.json',{'index_key':'fixture','events':groups})
            scenes=[{'id':str(i),'start':i*100,'end':i*100+35,'score':.9} for i in range(5)]
            fake=MagicMock();fake.eligible.side_effect=lambda s:s['id']!='0'
            fake.connect.return_value.__enter__.return_value.execute.return_value=[]
            with patch.object(event_discovery,'GameStore',return_value=fake):
                result=event_discovery.prioritized(scenes,r)
            self.assertNotIn('0',[s['id'] for s in result]);self.assertEqual(len(result),4)
    def test_corrected_concepts_still_reject_reused_source_frames(self):
        definitions=[('before_after','That robot is not answering.'),('discovery_reveal','A birthday message reaches the mountain.'),('cause_and_effect','Why did the snow suddenly move?')]
        scenes=[{'id':str(i),'start':i*100,'end':i*100+40} for i in range(3)]
        scan={'selected':0,'candidates':[{'structure':structure,'hook':hook,'windows':[{'scene_id':str(i),'start':i*100+j*8,'duration':8} for j in range(3)]} for i,(structure,hook) in enumerate(definitions)]}
        inspected=[(s['id'],s['start'],s['end']) for s in scenes]
        game_plan.validate_concepts(scan,scenes,{'duration':300},inspected)
        scan['candidates'][1]['windows'][2]['start']=108
        with self.assertRaisesRegex(ValueError,'Repeated footage'):game_plan.validate_concepts(scan,scenes,{'duration':300},inspected)
    def test_story_eligibility_keeps_evidence_gates(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            store=GameStore()
            scene={'recording':'r','confidence':.95,'score':.9,'rejected':None,'category':'failure','hashes_json':'["123"]','start':5,'end':35}
            with patch.object(store,'recording',return_value={'game':'fixture','sha256':'source'}):
                self.assertTrue(store.eligible(scene))
                for field,value in [('confidence',.3),('score',.1),('rejected','user rejected'),('category','menu')]:
                    self.assertFalse(store.eligible(dict(scene,**{field:value})))



    def test_proxy_sheet_uses_cached_proxy_and_preserves_absolute_origin(self):
        if not shutil.which('ffmpeg'):self.skipTest('ffmpeg required')
        with tempfile.TemporaryDirectory() as temp,patch.object(gs,'ROOT',Path(temp)):
            root=Path(temp);original=root/'original.webm';original.write_bytes(b'original fixture must not be decoded')
            meta={'source':str(original),'source_sha256':digest(original),'source_size_bytes':original.stat().st_size,'source_modified_ns':original.stat().st_mtime_ns,'duration':200}
            p=root/'project';save(p/'manifest.json',meta)
            r={'id':'r','sha256':meta['source_sha256'],'index_key':'fixture'}
            folder=root/'FootageIndex'/('sha256_'+r['sha256'])/'LocalFirst_fixture/chunk_00000';folder.mkdir(parents=True)
            proxy=folder/'analysis.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=blue:size=640x360:rate=2','-t','2','-c:v','libx264','-threads','1',str(proxy)],check=True)
            save(folder/'artifacts.json',{'start':100,'end':102,'files':{'analysis.mp4':digest(proxy)}})
            store=GameStore()
            with store.connect() as db:db.execute('INSERT INTO game_chunks VALUES (?,?,?,?,?,?,?,?)',('r','fixture',0,100,102,'complete','{}',None))
            scene={'recording':'r','chunk':0,'start':100,'end':102}
            with patch.object(GameStore,'recording',return_value=r):
                image=shared_index.dense_proxy(p,scene,100.5,1)
                self.assertGreater(image.stat().st_size,800)
                receipt=read(image.with_suffix('.json'));self.assertEqual(receipt['absolute_start'],100.5);self.assertEqual(receipt['proxy_origin'],100)
                modified=image.stat().st_mtime_ns
                self.assertEqual(shared_index.dense_proxy(p,scene,100.5,1),image)
                self.assertEqual(image.stat().st_mtime_ns,modified)
                with proxy.open('ab') as stream:stream.write(b'changed')
                with self.assertRaisesRegex(ValueError,'Proxy changed'):shared_index.dense_proxy(p,scene,100.5,1)
            self.assertEqual(original.read_bytes(),b'original fixture must not be decoded')

if __name__=='__main__':unittest.main()
