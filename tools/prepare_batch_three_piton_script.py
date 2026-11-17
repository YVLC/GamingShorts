from create_batch_three import v
from common import save,read
p,r,store,scenes,windows,images=v.setup('batch3_piton_routes')
revision={'reason':'Use the verified developer explanation without implying these illustrative walls reject pitons.',
 'narration':["You can climb almost anywhere in Cairn. But that doesn't mean you can anchor everywhere.",
    'Some surfaces deliberately block piton placement. The team designed these areas for climbing without those metal anchors.',
    'Pitons let Aava secure herself and rest. Plan those stops along with your next handhold. Subscribe for more.'],
 'caption_y':{'1':.82,'2':.82,'3':.82}}
save(p/'script_revision.json',revision)
if (p/'edit_plan.candidate.json').exists():
    doc=read(p/'edit_plan.candidate.json')
    for c,line in zip(doc['clips'],revision['narration']):c['narration']=line;c['caption']=line
    save(p/'authored_plan.json',doc)
print('Developer-backed piton route-planning fact prepared.')
