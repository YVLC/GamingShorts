"""Package the current tested source and delivered media receipts without overwrites."""
import json,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
release=ROOT/'Releases/2026-11-15-visual-stories-v2'
source=release/'source';source.mkdir(exist_ok=True)
for f in (ROOT/'Automation/gamingshorts_v2').iterdir():
    if f.is_file() and f.suffix in ('.py','.json','.md'):shutil.copy2(f,source/f.name)
for folder,patterns in [('tests',['test_subject_tracking.py','test_gaming_stories.py','render_smoke.py','render_word_handoff.py']),
                        ('tools',['create_visual_stories_v2.py','visual_story_speech.py','preview_visual_story.py','visual_preview_sheet.py','inspect_visual_delivery.py','package_visual_stories_v2.py'])]:
    dest=source/folder;dest.mkdir(exist_ok=True)
    base=ROOT/'Automation/gamingshorts_v2/tests' if folder=='tests' else ROOT/'tools'
    for name in patterns:shutil.copy2(base/name,dest/name)
manifest={str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in source.rglob('*') if f.is_file()}
(release/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
titles={'kami_history':'Who climbed Kami before Aava?', 'crafted_mountain':'Every rock was placed by hand', 'cave_traces':'Kami after dark'}
lines=['# Cairn visual stories v2','','Original stories from environmental discoveries, scenery and verified facts. No conversation-led narratives. Full-frame tracked 9:16 footage, free Garret narration, yellow active-word captions and cleared instrumental music.','']
for event,title in titles.items():
    receipt=release/(event+'_delivery.json')
    if not receipt.exists():continue
    data=json.loads(receipt.read_text());raw=data['output'].replace('/mnt/d/GamingShorts/','')
    target=ROOT/raw
    metadata=target.with_suffix('.upload.json')
    if metadata.exists():
        upload=json.loads(metadata.read_text())
        if upload['output_sha256']!=data['sha256']:raise ValueError('Upload metadata is bound to a different video')
        upload['title']={'kami_history':'Who was here before Aava? | Cairn Lore',
                         'crafted_mountain':'How Mount Kami was built | Cairn',
                         'cave_traces':'Kami after dark | Cairn'}[event]
        if '#Cairn' not in upload['description']:upload['description']+='\n#Cairn'
        metadata.write_text(json.dumps(upload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines+=['## '+title,'',f'[Watch the new clip](../../{target.relative_to(ROOT).as_posix()})','',f"SHA256: `{data['sha256']}`",'']
    q=data['qc'];lines+=[f"Technical QC: {q['status']}. Original footage and source cadence checked; final media decoded and mixed speech checked.",'']
    if q.get('warnings'):lines+=['Warnings: '+json.dumps(q['warnings']),'']
lines+=['## Validation and limits','','Regression results are in regression.log. Actual render smoke and yellow-caption handoff fixture results are in render_smoke.log and word_handoff.log. Framing previews are in crop_previews. Source facts and originality have independent reviews; technical QC is not publication approval. Human listening and full editorial playback remain manual. Previous exports and source footage are preserved. No automatic publication.','','No currently verified trending track was available; these clips use cleared instrumental tracks without claiming trend status.','','The cave-mystery draft was withheld after independent review rejected unclear object identification and unsupported spatial implications. No narration was generated for that rejected draft.','','## Factual sources','','[The Game Bakers: exploration and Kami’s earlier inhabitants](https://www.linkedin.com/posts/the-game-bakers_cairnis-more-than-just-a-climbing-game-activity-7404195649887547392-9zZ9). Verified paraphrase: exploration reveals traces of earlier expeditions and an older troglodyte culture.','','[The Game Bakers technical art director: building Mount Kami](https://legacy-activation.unity3d.com/blog/cairn-technical-art-rendering-gameplay-rock-materials). Verified paraphrase: designers positioned the mountain’s rocks manually.','','Creative hooks do not authorize invented factual secrets.','']
(release/'DELIVERY_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(release/'DELIVERY_REPORT.md')
