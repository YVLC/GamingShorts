import json
from pathlib import Path
from create_batch_three import v
from common import read,save,key,digest,HERE
from quality_checks import measure_cadence,rate
p=v.gs.ROOT/'Projects/V2/videoplayback_e772d2c8_visual_v2_batch3_chamber_light';doc=read(p/'edit_plan.json')
r=v.GameStore().recording();video=next(s for s in json.loads(r['probe_json'])['streams'] if s['codec_type']=='video');fps=rate(video['avg_frame_rate'])
entries=[]
for c in doc['clips']:
    seconds=min(3,float(c['duration']));token=key({'source':r['sha256'],'start':c['start'],'duration':seconds,'fps':str(fps),'qc':digest(HERE/'quality_checks.py')})
    receipt=v.gs.ROOT/'FootageIndex'/('sha256_'+r['sha256'])/'ProductionCadence'/(token+'.json')
    result=read(receipt)['result'] if receipt.exists() else measure_cadence(r['source'],c['start'],seconds,fps)
    if not receipt.exists():save(receipt,{'key':token,'result_key':key(result),'result':result})
    entries.append({'start':c['start'],'duration':c['duration'],'result_key':key(result),'measured_profile':result})
    print(c['start'],result.get('active_updates_per_second'),result.get('cadence_limited'),flush=True)
detail=read(v.RELEASE/'signage_detail_evidence.json')['images']
save(p/'source_context_cadence.json',{'purpose':'written_lore_with_ambient_context','source_sha256':r['sha256'],'plan_key':key(doc),
    'detail_images':{d['path']:d['sha256'] for d in detail},'entries':entries,
    'scope':'The story explains a readable inscription and ambient fire signage. Some original environmental animation updates at about 15 Hz inside a 60-fps file. Preserve its measured native cadence; do not interpolate frames or claim smooth 60-fps action.'})
