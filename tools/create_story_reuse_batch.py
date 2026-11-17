"""Three requested story-led edits from saved evidence; no full-source analysis."""
import sys,json,shutil,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,digest,config,locked,now
import gaming_shorts as gs,game_plan,editorial,creative_history,story_policy,music_library,voices,captions
from game_store import GameStore
from game_index import cached_ai,checked_recording
from start import prepare

RELEASE=gs.ROOT/'Releases/2026-11-15-story-reuse'
DEST=gs.ROOT/'ReadyForReview/cairn_stories_2026-11-15'
CHOICES={
 'crystal_lore':{'type':'lore','brief':'Explain why the glowing sanctuary is a burial place and why that changes the meaning of digging crystals. Add an interpretation of the ethical tension, not a subtitle reading or another philosophy-homework joke. Do not assert ownership or supernatural mechanics. The burial custom and Aava questioning the digging are the evidence.',
 'windows':[('15c034398d9fb95c68c1ed3c1407f70e',10322,8),('15c034398d9fb95c68c1ed3c1407f70e',10330,9),('15c034398d9fb95c68c1ed3c1407f70e',10339,9)]},
 'marco_choice':{'type':'emotional_story','brief':'Explore the tension between pushing a climbing partner and caring about him. In this exchange Aava urges Marco onward, he complains she will kill him before the mountain does, and she offers to descend with him. Describe her offer, never claim she actually descends or sacrifices the summit. Make the emotional meaning understandable without inventing romance, injury, death or unseen history.',
 'windows':[('fb3f16832eccf415a1a456063e51d7ac',16392,10),('fb3f16832eccf415a1a456063e51d7ac',16402,10),('fb3f16832eccf415a1a456063e51d7ac',16412,10)]},
 'rainbow_logic':{'type':'funny_moment','brief':'A humorous contrast between the campfire argument about finishing the bottle to shed pack weight and the later surreal rainbow walk. The chronology is real but the skipped interval is omitted downtime. Do not assert alcohol caused hallucination or identify an unverified drink/easter egg. Joke about the absurd contrast, not a generic scenic rainbow appreciation or a replacement for character dialogue.',
 'windows':[('5dc83cf62418ca513a3c25770bc6a76e',13216,8),('5dc83cf62418ca513a3c25770bc6a76e',13224,6),('337bd26cdb697ff7c53980eaddbd34b8',13324.5,8.5),('337bd26cdb697ff7c53980eaddbd34b8',13333,11)]},
}

def project(name,r):
    p=prepare(Path(r['source']),'story_reuse_'+name)
    m=read(p/'manifest.json');m['full_game']={'game':r['game'],'recording':r['id'],'index_key':r['index_key'],'batch':'user_story_reuse_20261115'}
    save(p/'manifest.json',m);return p

def plan_one(name,r,store):
    p=project(name,r);choice=CHOICES[name]
    scenes=store.scenes(r['id']);by_id={s['id']:s for s in scenes}
    windows=[dict(scene_id=s,start=a,duration=d) for s,a,d in choice['windows']]
    for w in windows:
        if not store.eligible(by_id[w['scene_id']],project=p):raise ValueError('Selected evidence is explicitly held or unavailable: '+w['scene_id'])
    import shared_index
    images=[shared_index.dense_proxy(p,by_id[w['scene_id']],w['start'],w['duration']) for w in windows]
    context={'brief':choice['brief'],'story_type':choice['type'],'windows':windows,
        'observations':[{k:by_id[s][k] for k in ('id','description','evidence','start','end')} for s in dict.fromkeys(w['scene_id'] for w in windows)],
        'history':editorial.history(p),'preferences':read(Path(editorial.__file__).with_name('preferences.json'))}
    if not (p/'edit_plan.json').exists():
        prompt=(story_policy.BRIEF+' Write ONE strong story script for the supplied exact windows. Use exactly those shots, durations and scene IDs, in source chronology. Each line should be speakable in its shot with a little room to breathe, generally 1.5-2 words per second or less. No opening_action. '+
            'Choose a canonical structure different from the recent two. Each beat must advance the story. Supply a concrete hook, added-value narration, supported payoff and final Subscribe for more. CTA belongs only in final shot. Set editorial.policy gaming-stories-v1 and story_type to the requested type. Keep captions short and meaningful. '+
            'The source recording has no gameplay speech/audio. Do not invent character audio. Frame inspection includes readable dialogue as evidence. Do not claim you heard speech. '+
            'Music: choose mood and allow_vocals true only when appropriate; prefer instrumentals. No tool calls or file edits. Return strict schema JSON. Context: '+json.dumps(context))
        doc=cached_ai(p/'StoryReuse',prompt,game_plan.PLAN,images,'narrative')
        if [(c['scene_id'],c['start'],c['duration']) for c in doc['clips']]!=[(w['scene_id'],w['start'],w['duration']) for w in windows]:raise ValueError('Script changed selected exact evidence windows')
        if doc['editorial']['story_type']!=choice['type']:raise ValueError('Script changed story angle')
        # Use a close portrait only where it preserves the important subject;
        # conversations and full-body scenes retain the source composition.
        for i,c in enumerate(doc['clips']):c.update(framing='dialogue_portrait' if name=='crystal_lore' or (name=='marco_choice' and i==0) else 'blur_contain')
        save(p/'edit_plan.candidate.json',doc)
        editorial.check_blueprint(p,doc);story_policy.validate(doc)
        review=cached_ai(p/'StoryReuse',story_policy.BRIEF+' Independently evaluate the exact script against attached timestamped source windows and supplied observations. No script claim is its own evidence. immediate_action means an immediately compelling hook, not mandatory physical movement. Reject dialogue dubbing, invented motives/outcomes, unsupported lore or a forced payoff. For Marco, distinguish offering to descend from actually descending. For rainbow, do not infer a causal intoxication claim. Return strict schema JSON. No tools. Plan: '+json.dumps(doc)+' Observations: '+json.dumps(context['observations']),game_plan.REVIEW,images,'evidence_review')
        if not story_policy.review_passes(review):
            save(p/'rejected_evidence.json',{'plan':doc,'review':review});raise ValueError('Evidence review rejected: '+json.dumps(review))
        creative_history.require_review(p,doc,invoke=True,images=images)
        store.reserve(p,doc,scenes)
        save(p/'evidence_review.json',{'plan_key':key(doc),'index_key':r['index_key'],'review':review,
            'story_identity':story_policy.receipt_identity(p,doc),'inspected':[(w['scene_id'],w['start'],w['start']+w['duration']) for w in windows]})
        save(p/'edit_plan.json',doc);editorial.remember(p)
    doc=gs.validate(p);creative_history.require_review(p,doc,invoke=True,images=images);game_plan.guard(p,doc)
    # Fail before any speech if the cleared local music cannot satisfy the plan.
    music=music_library.select(p)
    save(RELEASE/(name+'_plan.json'),{'project':str(p),'plan':doc,'music':music,'speech_request':voices.request(doc['clips'])})
    print(json.dumps({'event':name,'project':str(p),'script':[c['narration'] for c in doc['clips']],'music':music['title']}),flush=True)
    return p

def render_one(name,r):
    p=project(name,r);doc=gs.validate(p)
    import shared_index
    images=[shared_index.dense(p,c['start'],c['duration']) for c in doc['clips']]
    creative_history.require_review(p,doc,invoke=True,images=images);game_plan.guard(p,doc)
    music_library.select(p)
    voice=voices.ensure(p,doc['clips']);captions.align(p)
    final=game_plan.render(p,voice);q=read(p/'qc_report.json')
    DEST.mkdir(parents=True,exist_ok=True);target=DEST/final.name
    if target.exists() and digest(target)!=digest(final):raise ValueError('Prior review output would be overwritten')
    if not target.exists():shutil.copy2(final,target)
    from upload_metadata import write_metadata
    write_metadata(p)
    for ext in ('.srt','.captions.json','.music.txt','.upload.json'):
        side=final.with_suffix(ext)
        if side.exists():shutil.copy2(side,target.with_suffix(ext))
    editorial.remember(p,'validated')
    save(RELEASE/(name+'_delivery.json'),dict(output=str(target),sha256=digest(target),qc=q))
    print(json.dumps({'event':name,'output':str(target),'status':q['status']}),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['plan','render']);parser.add_argument('--event',choices=list(CHOICES));a=parser.parse_args()
    RELEASE.mkdir(parents=True,exist_ok=True)
    with locked(gs.ROOT/'Database/.full_analysis_mission.lock'),locked(gs.ROOT/'Database/.workflow_v2.lock'):
        store=GameStore();r=store.recording();checked_recording(r)
        for name in ([a.event] if a.event else CHOICES):
            print('STAGE '+a.stage+' '+name,flush=True)
            if a.stage=='plan':plan_one(name,r,store)
            else:render_one(name,r)

if __name__=='__main__':main()
