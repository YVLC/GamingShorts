from pathlib import Path
from create_batch_three import v
from common import read,save
p=v.gs.ROOT/'Projects/V2/videoplayback_e772d2c8_visual_v2_batch3_camp_coffee'
doc=read(p/'edit_plan.candidate.json');ed=doc['editorial']
ed['payoff']='An elaborate drinks-menu detour resolves into one finished Coffee result.'
ed['evidence']='The source shows pouring, ingredient cards including coffee packet, booze and alpine cola, then a clearly labeled Coffee result and vessel handling.'
ed['payoff_evidence']='The final window shows the Coffee result card; no sip or drinking is asserted.'
ed['beats']=['Cold-open on the pouring action and expedition drinks-menu joke.',
    'Browse the coffee and other drink choices without asserting their addition.',
    'Build the airport-lounge/beverage-department comparison.',
    'End on the finished Coffee result and closing CTA.']
ed['claims'][-1]={'claim':'The finished result is Coffee.','evidence':'A readable Coffee result card appears in the final window.','basis':'footage','reference_id':''}
lines=[c['narration'] for c in doc['clips']];lines[-1]='An entire beverage department. One coffee. Subscribe for more.'
revision={'reason':'End on the supported Coffee result, not an unproved sip. Follow ingredient labels in the vertical crop.',
    'narration':lines,'editorial':ed,
    'clip_evidence':{'4':'The Coffee result card and subsequent vessel handling; no drinking or physical effect is inferred.'},
    'tracking':{'2':[{'at':0,'x':.51,'cut':False},{'at':1,'x':.51,'cut':False},{'at':1.5,'x':.25,'cut':False},{'at':7.9,'x':.25,'cut':False}],
        '3':[{'at':0,'x':.25,'cut':False}]}}
save(p/'script_revision.json',revision)
doc['editorial']=ed
for c,line in zip(doc['clips'],lines):c['narration']=line;c['caption']=line
doc['clips'][3]['evidence']=revision['clip_evidence']['4']
save(p/'authored_plan.json',doc)
print('Coffee script ends on the verified result card.')
