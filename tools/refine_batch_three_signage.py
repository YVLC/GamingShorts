from pathlib import Path
from create_batch_three import v
from common import save,digest,read
import shutil
r=v.GameStore().recording();image=v.RELEASE/'signage_text.png'
save(v.RELEASE/'signage_detail_evidence.json',{'images':[{'path':str(image),'sha256':digest(image),
    'source_sha256':r['sha256'],'at':14384,'crop':'1900:1800:1800:180',
    'purpose':'Readable original-source Troglodyte signage codes; no generated or retouched content.'}]})
p=v.gs.ROOT/'Projects/V2/videoplayback_e772d2c8_visual_v2_batch3_chamber_light'
revision={'reason':'Specific original-source lore replaces generic scene description.',
    'narration':['These flames are messages to the mountain.','The troglodytes used fire lines as signage.',
        'Three lines announce a summit attempt. Two mark a descent, and returning alive is celebrated.',
        'One means summit conquered. Impostors will be cursed, the inscription warns.',
        'Climbing history, written in fire. Subscribe for more.'],
    'caption_y':{'1':.12,'2':.12,'3':.86,'4':.86,'5':.82},
    'trim_bottom':{'1':.14,'2':.14},
    'tracking':{'1':[{'at':0,'x':.5,'cut':False},{'at':6.1,'x':.5,'cut':False},{'at':6.7,'x':.815,'cut':False}],
        '2':[{'at':0,'x':.5,'cut':False}],
        '3':[{'at':0,'x':.83,'cut':False}], '4':[{'at':0,'x':.83,'cut':False}]}}
save(p/'script_revision.json',revision)
base=p/'edit_plan.json' if (p/'edit_plan.json').exists() else p/'edit_plan.candidate.json'
if base.exists():
    doc=read(base)
    for c,(sid,start,duration),line in zip(doc['clips'],v.CHOICES['batch3_chamber_light']['windows'],revision['narration']):
        c.update(scene_id=sid,start=start,duration=duration,narration=line,caption=line)
    doc['clips'][0]['evidence']='The chamber contains burning horizontal wall strips, followed by another signage inspection.'
    doc['clips'][1]['evidence']='The smaller wall sign has a lighting interaction prompt; no activation method is inferred.'
    save(p/'authored_plan.json',doc)
    if (p/'edit_plan.json').exists():
        import time
        shutil.move(p/'edit_plan.json',p/f'edit_plan.before_signage_timing_{time.time_ns()}.json')
print('Original-source signage detail and lore script prepared.')
