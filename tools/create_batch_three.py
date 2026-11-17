"""Curated batch through the application planner, reviews, ledger and renderer."""
import sys,json
import create_visual_stories_v2 as v
from common import read,save,now,locked
v.RELEASE=v.gs.ROOT/'Releases/2026-11-15-batch-three'
v.DEST=v.gs.ROOT/'ReadyForReview/cairn_batch_three_20261115'
v.BATCH_ID='visual_batch_three_20261115'
v.CHOICES={
 'batch3_hand_grip':{'type':'beginner_tip','basis':'gameplay_demonstration','structure':'mechanic_demo','refs':[],
 'brief':'A practical hand-care tip: inspect BOTH hands and wrap damaged fingers with bandage tape. The footage shows repeated wrapping and ends with Excellent condition and Maximal grip. Explain the visible check-wrap-recheck sequence, not real-world medical advice, buttons you cannot see, invented stamina percentages or an invisible climb result. The payoff must clearly show both hands improved. Keep each line natural, not simply reading the menu.',
 'windows':[('e6fe9428ace3af65329ce696d6798ff1',9397,9),('e6fe9428ace3af65329ce696d6798ff1',9406,12),('e6fe9428ace3af65329ce696d6798ff1',9419,7.5),('e6fe9428ace3af65329ce696d6798ff1',9428.5,2.5)]},
 'batch3_chamber_light':{'type':'lore','basis':'world_lore','structure':'discovery_reveal','refs':[],'native_lore_context':True,
 'brief':'Decode the specific lore in the readable ORIGINAL-resolution inscription attached as detail evidence, not generic advice about supplies. It says Troglodyte signage codes are signs addressed to surrounding mountains: three FIRE lines indicate an attempt to climb the summit, two indicate descent and returning alive is celebrated, one is reserved for summit conquerors; impostors will be cursed. Treat the curse as the inscription\'s warning, not an observed debuff or trap. Explain why the visible fire lines are a climbing-status language and what the codes mean. This is environmental written lore, not an NPC conversation or a puzzle-unlock claim. Begin on the small symbol and flames; use the larger inscription to substantiate the three/two/one meanings, then finish over the lit chamber before its blackout. Do not invent the activation procedure, claim the diagram is required, or tie unrelated water pickups into this story.',
 'context':{'anchor_scene_id':'e79b1239cd648fd45da52ee7f81f636f','supporting_scene_ids':['d5d75b741123749fc00c60a0fb09ff3a','9209666df3a4952fd6fc056dcdaa3c64'],'purpose':'The original-resolution inscription decodes the meaning of the fire lines; the illuminated chamber places the written lore in its physical setting.'},
 'windows':[('e79b1239cd648fd45da52ee7f81f636f',14396,7),('e79b1239cd648fd45da52ee7f81f636f',14392,4),('d5d75b741123749fc00c60a0fb09ff3a',14378,6),('d5d75b741123749fc00c60a0fb09ff3a',14384,5.5),('9209666df3a4952fd6fc056dcdaa3c64',14426,4.2)]},
 'batch3_camp_coffee':{'type':'funny_moment','basis':'gameplay_demonstration','structure':'cause_and_effect','refs':[],
 'brief':'A dryly funny camping-coffee story. Open on the actual pouring action as a cold open, then cut back to the ingredient browsing, then forward to the finished coffee and drinking. No source interval is replayed. This is an edited cold open, not a claim of uninterrupted chronology. Use a concrete comic hook about an expedition getting a drinks menu. The interesting comic detail is the menu offering booze and other drinks during a mountain coffee break; do not claim those were added unless the action proves it. Pay off with coffee and a sip. Do not invent buffs, recipe requirements, a hangover or subsequent fall. Humorous comparisons are commentary. Keep menu commentary concise and purposeful; no character dialogue.',
 'windows':[('884fd0e7ac5406bcc3711eecdfb748d5',19364,5),('884fd0e7ac5406bcc3711eecdfb748d5',19346,8),('884fd0e7ac5406bcc3711eecdfb748d5',19357,7),('79ad328a46326063e88f9d1e4ecad6d7',19374,8)]}}

v.CHOICES['batch3_pack_break']={'type':'beginner_tip','basis':'gameplay_demonstration','structure':'cause_and_effect','refs':[],
 'brief':'A specific route-planning tip demonstrated in one local sequence: while hanging on the wall, the open pack explicitly says Backpack contents are not accessible while climbing. The climber then ascends to a pale ledge, gets feet supported, pauses upright and opens the usable inventory at the stopping point. Explain why a stable stopping point matters for managing supplies, not just gaining height. Do not claim an invisible stamina refill, invulnerability, food consumption or that every tiny ledge is safe. Distinguish opening the backpack interface from accessing its contents: the interface CAN open while climbing. Hook with the supply restriction over actual climbing, show the warning, then the ascent and stable stop before the inventory payoff. This is a new concrete procedure, not generic climbing motivation.',
 'context':{'anchor_scene_id':'7dfaea2352aa8afd3a4bd6f0346ce6fe','supporting_scene_ids':['efd78945a06f231c1b7d2d7908bcf1ed','26cde78dd29da5e9c4bab0f2a5a745bf','90bcfb541832c66a9a6ee2df4719e5d8','23408e61c4e2fc40d9e860f795211f0e'],'purpose':'The on-wall inventory warning and nearby ascent establish why the ledge pause matters; the immediately following open inventory supplies the practical payoff.'},
 'windows':[('efd78945a06f231c1b7d2d7908bcf1ed',15509,3),('26cde78dd29da5e9c4bab0f2a5a745bf',15518,4),('90bcfb541832c66a9a6ee2df4719e5d8',15560,8),('7dfaea2352aa8afd3a4bd6f0346ce6fe',15568,8),('7dfaea2352aa8afd3a4bd6f0346ce6fe',15576,5),('23408e61c4e2fc40d9e860f795211f0e',15584,4)]}
v.SOURCES['piton_surfaces']={'id':'piton_surfaces','url':'https://legacy-activation.unity3d.com/blog/cairn-technical-art-rendering-gameplay-rock-materials',
 'excerpt':'The Game Bakers technical art director explains that Aava can climb almost every wall. Pitons let her secure herself to a wall for rest. The team deliberately created specific areas that disallow planting pitons, requiring climbs without placing them.','excerpt_kind':'verified paraphrase','verified':True,'checked_date':'2026-11-16'}
v.CHOICES['batch3_piton_routes']={'type':'game_fact','basis':'gameplay_demonstration','structure':'cause_and_effect','refs':['piton_surfaces'],
 'brief':'Explain the verified developer design fact that climbable does not always mean a piton can be planted: certain surfaces deliberately disallow pitons. Pitons let Aava secure herself for rest. Use the supplied climbing footage as illustration of route planning; do NOT identify these particular walls as restricted, invent a refused placement, show an unseen piton plant or claim a fall. The primary developer reference establishes the mechanic. The useful insight is to plan possible rest/anchor points as well as handholds. This is an evidenced game fact with relevant illustrative gameplay, not a step-by-step demonstration of placing a piton. Do not repeat the earlier hand-placed-rocks design fact.',
 'windows':[('c642ff3873e1fe9a34cfd119b70d7f9b',5508,9),('48a784c02a885ebe9c1ea6edabe46470',5544,9),('c2b7a6e4200a053d62b168cf82d0104b',5575,9)]}
v.CHOICES={name:v.CHOICES[name] for name in ('batch3_chamber_light','batch3_piton_routes','batch3_hand_grip')}
detail=v.RELEASE/'signage_detail_evidence.json'
if detail.exists():v.CHOICES['batch3_chamber_light']['detail_evidence']=read(detail)['images']

if __name__=='__main__':
    v.RELEASE.mkdir(exist_ok=True)
    store=v.GameStore();r=store.recording()
    with locked(v.gs.ROOT/'Database/.workflow_v2.lock'):
        with store.connect() as db:
            db.execute("INSERT OR IGNORE INTO game_batches VALUES (?,?,?,?,?,'planning',NULL,?)",(v.BATCH_ID,r['game'],r['id'],r['index_key'],3,now()))
    error=None
    try:v.main()
    except BaseException as exc:
        error=str(exc);raise
    finally:
        with locked(v.gs.ROOT/'Database/.workflow_v2.lock'):
            with store.connect() as db:
                for i,name in enumerate(v.CHOICES):
                    info=v.RELEASE/(name+'_inspection.json')
                    if info.exists():db.execute('INSERT OR REPLACE INTO game_batch_items VALUES (?,?,?,?,NULL)',(v.BATCH_ID,i,read(info)['project'],json.dumps(v.CHOICES[name])))
                status='needs_attention' if error else 'ready_for_review' if all((v.RELEASE/(n+'_delivery.json')).exists() for n in v.CHOICES) else 'planned' if all((v.RELEASE/(n+'_plan.json')).exists() for n in v.CHOICES) else 'planning'
                db.execute('UPDATE game_batches SET status=?,error=? WHERE id=?',(status,error,v.BATCH_ID))
