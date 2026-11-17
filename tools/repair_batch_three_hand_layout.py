import json,shutil
from pathlib import Path
from create_batch_three import v
from common import read,save
p=v.gs.ROOT/'Projects/V2/videoplayback_e772d2c8_visual_v2_batch3_hand_grip'
doc=read(p/'edit_plan.json') if (p/'edit_plan.json').exists() else read(p/'edit_plan.candidate.json')
revision={'reason':'Focus the practical tip on the visible Worrisome warning, wrapping action, Excellent condition and Maximal grip rather than promising a simultaneous comparison of both hands.',
    'narration':['Worrisome condition? Check your fingers before the next wall. Cairn lets you inspect and tape damaged fingers.',
        'Select a damaged finger, then wrap it with bandage tape. Repeat where needed, and check the condition again before moving on.',
        'Finish wrapping, then reopen the inspection. Look for the updated condition before moving on.',
        'Excellent. Subscribe for more.'],
    'editorial':{'premise':'Inspect damaged fingers, apply bandage tape, and recheck the visible hand-condition result.',
        'evidence':'Worrisome hand-condition label, repeated wrapping animations, then Excellent condition in the final inspection.',
        'narration_added_value':'Explains a useful inspect-wrap-recheck routine, with the visible improved condition as the completion check.',
        'novelty_reason':'A practical hand-maintenance procedure with a visible result, distinct from the approved lore and landscape fact clips.',
        'hook_promise':'Show how the Worrisome hand condition can be checked and treated in this game sequence.',
        'payoff':'The final inspection displays Excellent condition.',
        'payoff_evidence':'The final source window begins after the improved condition label appears, before the brief closing CTA.',
        'viewer_value':'Learn the inspect-wrap-recheck procedure for damaged fingers in Cairn.',
        'beats':['Notice the Worrisome condition label.','Select and wrap damaged fingers.','Recheck the improved condition and grip labels.'],
        'claims':[{'claim':'The initial inspection shows Worrisome hand condition.','evidence':'Readable right-hand condition label in the first window.','basis':'footage','reference_id':''},
            {'claim':'Damaged fingers can be wrapped with bandage tape.','evidence':'The Wrap bandage tape prompt and repeated wrapping animations.','basis':'footage','reference_id':''},
            {'claim':'The later inspection shows Excellent condition.','evidence':'The final inspection label following the wrapping sequence.','basis':'footage','reference_id':''}]},
    'caption_y':{'1':.82,'2':.82,'3':.82,'4':.82},
    'tracking':{'1':[{'at':t,'x':x,'cut':False} for t,x in [(0,.73),(3.5,.73),(4.5,.5),(9,.5)]],
                '3':[{'at':0,'x':.5,'cut':False}],
                '4':[{'at':0,'x':.73,'cut':False}]}}
save(p/'script_revision.json',revision)
if (p/'edit_plan.json').exists():shutil.move(p/'edit_plan.json',p/'edit_plan.before_final_inspection_timing.json')
print('Revised script and crop timing before narration generation.')
