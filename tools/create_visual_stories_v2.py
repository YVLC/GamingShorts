"""World-led Cairn stories: native full-frame tracking, no conversation montages."""
import sys,json,argparse,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,digest,config,run,locked
import gaming_shorts as gs,game_plan,editorial,creative_history,story_policy,music_library,voices,captions,shared_index,render_sources
from game_store import GameStore
from game_index import cached_ai,checked_recording
from start import prepare
RELEASE=gs.ROOT/'Releases/2026-11-15-visual-stories-v2';DEST=gs.ROOT/'ReadyForReview/cairn_visual_stories_v2'
BATCH_ID='visual_stories_v2_20261115'
SOURCES={
 'world_past':{'id':'world_past','url':'https://www.linkedin.com/posts/the-game-bakers_cairnis-more-than-just-a-climbing-game-activity-7404195649887547392-9zZ9','excerpt':'The studio states that exploration uncovers evidence of earlier climbing parties and remains of an old troglodyte civilization.','excerpt_kind':'verified paraphrase','verified':True,'checked_date':'2026-11-15'},
 'handbuilt':{'id':'handbuilt','url':'https://legacy-activation.unity3d.com/blog/cairn-technical-art-rendering-gameplay-rock-materials','excerpt':'The technical art director explains that Mount Kami is assembled in three dimensions, with every rock positioned manually by designers.','excerpt_kind':'verified paraphrase','verified':True,'checked_date':'2026-11-15'}}
CHOICES={
 'kami_history':{'type':'lore','basis':'world_lore','structure':'environmental_lore','refs':['world_past'],
 'brief':'Who was on this mountain before Aava? Tell the environmental story using the wall opening, glowing cavern, cliffside architecture and an item explicitly named Troglodyte piton. Connect the visible traces to the officially confirmed older culture. Do not infer that every individual building or crystal has a specific religious function or owner. Do not discuss NPC conversations, cemetery ethics or Marco. The payoff is that Kami is a place with a human past, not an empty obstacle.',
 'windows':[('c642ff3873e1fe9a34cfd119b70d7f9b',5498,6),('d815aa6d4e898b1313199de794e25de0',10265,7),('4d176a9fbd3c0e784e6d0e834909d78b',14538,8),('c1d852cd9d4a4d821bf88d90114a0022',18016,6)]},
 'crafted_mountain':{'type':'game_fact','basis':'scenery','structure':'design_insight','refs':['handbuilt'],
 'brief':'Explain the surprising verified design fact that Kami is not a randomly generated pile of rock: the developers placed its rocks by hand. Use the sunset overlook and detailed climbing surfaces to show a mountain that is both scenery and designed routes. Do not claim a procedural system exists, every hold is safe, or the footage proves technical internals; the developer reference proves the design fact. No NPC or conversation stories.',
 'windows':[('6599c92cc75181b0f0c1a460d5ef397d',2304,8),('48a784c02a885ebe9c1ea6edabe46470',5536,8),('c2b7a6e4200a053d62b168cf82d0104b',5562,9)]},
 'cave_traces':{'type':'scary_moment','basis':'visual_discovery','structure':'atmosphere_reveal','refs':['world_past'],
 'brief':'Build a short environmental mystery contrasting a peaceful nighttime mountain view with a headlamp discovery and unsettling hanging shapes in a cave. This is a thematic montage of separate places/times, not a claimed continuous route. Show traces of other journeys; the official reference confirms earlier expeditions exist in the world. Do not invent monsters, a murder, a named dead person, a cause of death, a hidden ending or an explanation for the unclear shapes. The payoff is the atmosphere and discovery itself, not a promised identity reveal. No character conversations or analysis of dialogue.',
 'windows':[('0835a1d0f896387f820265de3e3cc5e1',13200,8),('4b50c61e7da16058f8bfddcd9919ef93',8670,5),('c81d895ef0c7378741519babd05320f8',8690,12)]}}

def setup(name):
    store=GameStore();r=store.recording();checked_recording(r);choice=CHOICES[name]
    p=prepare(Path(r['source']),'visual_v2_'+name)
    m=read(p/'manifest.json');m['full_game']={'game':r['game'],'recording':r['id'],'index_key':r['index_key'],'batch':BATCH_ID};save(p/'manifest.json',m)
    save(p/'research.json',{'sources':[SOURCES[k] for k in choice['refs']]})
    if choice.get('context'):
        save(p/'scene_context.json',dict(choice['context'],source_sha256=r['sha256']))
    scenes=store.scenes();by_id={s['id']:s for s in scenes};windows=[dict(scene_id=s,start=a,duration=d) for s,a,d in choice['windows']]
    for w in windows:
        if not store.eligible(by_id[w['scene_id']],project=p):raise ValueError('Unavailable/rejected source evidence: '+w['scene_id'])
    images=[shared_index.dense_proxy(p,by_id[w['scene_id']],w['start'],w['duration']) for w in windows]
    for detail in choice.get('detail_evidence',[]):
        path=Path(detail['path'])
        if detail['source_sha256']!=r['sha256'] or digest(path)!=detail['sha256'] or not any(w['start']<=detail['at']<=w['start']+w['duration'] for w in windows):
            raise ValueError('Detail image is not bound to this inspected source window')
        images.append(path)
    save(RELEASE/(name+'_inspection.json'),{'project':str(p),'windows':windows,'images':[str(x) for x in images],
        'detail_evidence':choice.get('detail_evidence',[]),
        'observations':[{k:by_id[s][k] for k in ('id','description','evidence','start','end')} for s in dict.fromkeys(w['scene_id'] for w in windows)]})
    return p,r,store,scenes,windows,images

def plan_one(name):
    p,r,store,scenes,windows,images=setup(name);choice=CHOICES[name]
    if not (p/'edit_plan.json').exists():
        context=read(RELEASE/(name+'_inspection.json'))|{'brief':choice['brief'],'type':choice['type'],'basis':choice['basis'],'structure':choice['structure'],'research':story_policy.references(p),'quality_reference':__import__('quality_reference').context()}
        prompt=(story_policy.BRIEF+' Write ONE original visually led Cairn Short, using exactly the supplied windows, source IDs and durations. Set the requested story_type, story_basis and structure. No NPC conversation as the central event. State the useful/interesting discovery clearly, rather than a vague moral or generic scenery appreciation. Use a strong concrete hook, 3-4 advancing beats, a supported payoff, and Subscribe for more. at the end. '+
            'Keep each line concise enough to speak naturally in its exact shot, generally no more than 2 words per second. Garret is the external narrator. Do not assert facts from a proposed script; use the inspected images and verified research. '+
            'For every clip use framing tracked_cover, supply a conservative tracking path with at=0 then subject-position keyframes in clip-local seconds, normalized source x values, cut=true only at actual source camera cuts. Choose caption_y between .12 and .88 away from the important subject. Do not use blur fillers or invent off-screen content. No opening_action or generic introduction. Return strict schema JSON only, no tools. Context: '+json.dumps(context))
        if (p/'rejected_evidence.json').exists():
            prompt+=' Correct this rejected draft and every listed issue without introducing unsupported claims: '+json.dumps(read(p/'rejected_evidence.json'))
        # A deliberately edited draft still goes through every independent
        # source, originality and crop check; it is not an evidence receipt.
        doc=read(p/'authored_plan.json') if (p/'authored_plan.json').exists() else cached_ai(p/'VisualStoriesV2',prompt,game_plan.PLAN,images,'narrative')
        revision=p/'script_revision.json'
        if revision.exists():
            lines=read(revision)['narration']
            if len(lines)!=len(doc['clips']):raise ValueError('Script revision changed shot count')
            for clip,line in zip(doc['clips'],lines):
                clip['narration']=line;clip['caption']=line
            for index,y in read(revision).get('caption_y',{}).items():
                doc['clips'][int(index)-1]['caption_y']=y
            for field in ('trim_top','trim_bottom'):
                for index,value in read(revision).get(field,{}).items():
                    doc['clips'][int(index)-1][field]=value
            for index,path in read(revision).get('tracking',{}).items():
                doc['clips'][int(index)-1]['tracking']=path
            for index,evidence in read(revision).get('clip_evidence',{}).items():
                doc['clips'][int(index)-1]['evidence']=evidence
            doc['editorial'].update(read(revision).get('editorial',{}))
        # The legacy static hook field is short; full spoken captions come from
        # the complete narration and real word timestamps, never this summary.
        for clip in doc['clips']:
            words=clip['caption'].split()
            while words:
                try:
                    gs.caption_lines(' '.join(words))
                    if len(' '.join(words))<=60:break
                except ValueError:
                    pass
                words.pop()
            clip['caption']=' '.join(words)
        if [(c['scene_id'],c['start'],c['duration']) for c in doc['clips']]!=[(w['scene_id'],w['start'],w['duration']) for w in windows]:raise ValueError('Narrative changed the selected exact windows')
        if doc['editorial']['story_type']!=choice['type'] or doc['editorial']['story_basis']!=choice['basis']:raise ValueError('Narrative changed the visual story foundation')
        story_policy.validate(doc,story_policy.references(p));editorial.check_blueprint(p,doc)
        save(p/'edit_plan.candidate.json',doc)
        review=cached_ai(p/'VisualStoriesV2',story_policy.BRIEF+' Independently review SOURCE FACTS, STORY and SCRIPT against these inspected original-source windows and the supplied verified developer references. visual_story must reject conversation-derived scenes and interpersonal analyses. A source reference can establish external design/lore facts; images establish what the footage actually shows. Reject invented identities, mechanics, outcomes, route continuity or supernatural explanations. This is source/script review; audio, final crop and captions are checked after rendering and must not be claimed as heard/seen here. Expected later production checks are not source/script defects: reserve issues for actual problems in the proposed source facts or story, not reminders that narration and final media have not been produced yet. immediate_action means an immediate compelling visual-story hook, including scenery. Return strict JSON, no tools. Plan: '+json.dumps(doc)+' Research: '+json.dumps(story_policy.references(p)),game_plan.REVIEW,images,'source_review')
        if not story_policy.review_passes(review):save(p/'rejected_evidence.json',{'plan':doc,'review':review});raise ValueError('Source/story review rejected: '+json.dumps(review))
        creative_history.require_review(p,doc,invoke=True,images=images)
        store.reserve(p,doc,scenes)
        save(p/'evidence_review.json',{'plan_key':key(doc),'index_key':r['index_key'],'review':review,'story_identity':story_policy.receipt_identity(p,doc),'inspected':[(w['scene_id'],w['start'],w['start']+w['duration']) for w in windows]})
        save(p/'edit_plan.json',doc);editorial.remember(p)
    doc=gs.validate(p);game_plan.guard(p,doc)
    if choice.get('native_lore_context'):
        from source_context_cadence import record_context
        record_context(p,doc,r,choice['detail_evidence'])
    game_plan.preflight(p,doc)
    selected=music_library.select(p)
    save(RELEASE/(name+'_plan.json'),{'project':str(p),'plan':doc,'music':selected,'speech_request':voices.request(doc['clips'])})
    print(json.dumps({'event':name,'script':[c['narration'] for c in doc['clips']],'music':selected['title']}),flush=True)

def preview_one(name):
    meta=read(RELEASE/(name+'_plan.json'));p=Path(meta['project']);doc=read(p/'edit_plan.json');m=read(p/'manifest.json');cfg=config();folder=RELEASE/'crop_previews'/name;folder.mkdir(parents=True,exist_ok=True)
    for i,c in enumerate(doc['clips'],1):
        source=render_sources.resolve(m,c,gs.probe);source.update(tracking=c['tracking'],caption_y=c['caption_y'],trim_top=c.get('trim_top',0),trim_bottom=c.get('trim_bottom',0));graph,framing=render_sources.picture_filters(source,cfg,'tracked_cover')
        # Decode from the clip start so tracking t is identical to production.
        for label,t in [('start',.3),('middle',c['duration']/2),('end',c['duration']-.3)]:
            vf='setpts=PTS-STARTPTS,'+graph+f",select='gte(t,{t})'"
            run(['ffmpeg','-v','error','-nostdin','-y','-ss',c['start'],'-i',source['path'],'-vf',vf,'-frames:v','1',folder/f'shot_{i:02d}_{label}.jpg'])
        save(folder/f'shot_{i:02d}_geometry.json',framing)
    print(name+' full-screen crop previews ready',flush=True)

def render_one(name):
    meta=read(RELEASE/(name+'_plan.json'));p=Path(meta['project']);doc=gs.validate(p)
    images=[shared_index.dense(p,c['start'],c['duration']) for c in doc['clips']]
    creative_history.require_review(p,doc,invoke=True,images=images);game_plan.guard(p,doc)
    voice=voices.ensure(p,doc['clips']);captions.align(p);final=game_plan.render(p,voice);q=read(p/'qc_report.json')
    DEST.mkdir(parents=True,exist_ok=True);target=DEST/final.name
    if target.exists() and digest(target)!=digest(final):raise ValueError('Refusing to replace an earlier output')
    if not target.exists():shutil.copy2(final,target)
    from upload_metadata import write_metadata
    write_metadata(p)
    for ext in ('.srt','.captions.json','.music.txt','.upload.json'):
        if final.with_suffix(ext).exists():shutil.copy2(final.with_suffix(ext),target.with_suffix(ext))
    editorial.remember(p,'validated');save(RELEASE/(name+'_delivery.json'),{'output':str(target),'sha256':digest(target),'qc':q})
    print(json.dumps({'event':name,'output':str(target),'status':q['status']}),flush=True)

def main():
    a=argparse.ArgumentParser();a.add_argument('stage',choices=['inspect','plan','preview','render']);a.add_argument('--event',choices=list(CHOICES));args=a.parse_args();RELEASE.mkdir(parents=True,exist_ok=True)
    with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
        for name in ([args.event] if args.event else CHOICES):
            print(args.stage+' '+name,flush=True)
            if args.stage=='inspect':setup(name)
            elif args.stage=='plan':plan_one(name)
            elif args.stage=='preview':preview_one(name)
            else:render_one(name)

if __name__=='__main__':main()
