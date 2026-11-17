"""Reproducible source release and three review-ready exports; never publishes."""
import shutil
from pathlib import Path
from create_batch_three import v
from common import read,save,digest,HERE
titles={'batch3_hand_grip':'Check your fingers before the next wall | Cairn tips',
    'batch3_chamber_light':'A language written in fire | Cairn lore',
    'batch3_piton_routes':'Why some surfaces refuse pitons | Cairn'}
lines=['# Cairn: three new clips','','New source-driven stories following the user-approved visual-stories-v2 reference. All three use original footage, tracked full-screen 1080×1920 framing, free Garret narration, real-timestamp yellow word highlights, cleared instrumental music and a closing Subscribe for more.','']
for name,title in titles.items():
    delivery=read(v.RELEASE/(name+'_delivery.json'));video=Path(delivery['output']);q=delivery['qc']
    if q['status']!='technical_pass' or digest(video)!=delivery['sha256']:raise ValueError('Delivered output changed or failed QC')
    meta_path=video.with_suffix('.upload.json');meta=read(meta_path)
    if meta['output_sha256']!=delivery['sha256']:raise ValueError('Upload metadata refers to a different video')
    meta['title']=title
    if '#Cairn' not in meta['description']:meta['description']+='\n#Cairn'
    save(meta_path,meta)
    verification=read(v.RELEASE/'actual_frames'/name/'verification.json')
    if verification.get('unexplained_black_events'):raise ValueError('Unexplained black frames remain')
    lines+=['## '+title,'',f'[Watch the clip](../../{video.relative_to(v.gs.ROOT).as_posix()})','',f"Duration: {verification['duration']:.2f}s. Technical QC passed; no unexplained black frames. SHA256: `{delivery['sha256']}`.",'']
    if verification.get('source_transition_evidence'):lines+=['A brief 0.18-second native hand-inspection blink is preserved and matched against the original source; evidence is saved with the final-frame checks.','']
    if name=='batch3_chamber_light':lines+=['The inscription is readable in the [original-source detail](signage_text.png). Its curse is presented as the written warning, not a demonstrated game effect. The source-native inspection/ambient animation cadence is retained and documented in the project’s source_context_cadence.json; no interpolated frames or smooth 60-fps action claim is made.','']
    if name=='batch3_piton_routes':lines+=['The mechanic is supported by [The Game Bakers technical art director’s explanation](https://legacy-activation.unity3d.com/blog/cairn-technical-art-rendering-gameplay-rock-materials). The climbing shots are illustrative; these specific walls are not identified as restricted and no failed piton attempt is invented.','']
    if q.get('warnings'):lines+=['Caption/readability review notes: '+str(q['warnings']),'']
lines+=['## Evidence and validation','','The hand-care procedure and fire-signage lore come from the recording. The piton design fact additionally uses the primary developer reference linked above. No invented buffs, secret doors or NPC conversation stories are used. Source/script, originality and sampled crop/caption checks were completed before narration. Real rendered media was decoded and checked for speech presence, mix correlation and preservation of source cadence. Black-frame checks distinguish the documented native hand-inspection blink from unexplained missing footage. Actual hook, mid-clip and CTA samples are in actual_frames/.','','The chamber includes nearby diagram and room-reveal footage as explicit context for its fire signage. Supporting scenes remain bound to the source and a high-confidence central event, with rejection/exclusion safeguards and a minimum central-event share. The hand-care payoff is placed after the improved condition appears. The coffee draft was withheld because its action footage did not pass the source-motion check; no coffee narration was generated.','','Regression and actual-render results are in regression.log and render_smoke.log. Caption previews use the production ASS layout and sample held tracking positions. Human listening and full editorial playback remain manual; technical QC is not user approval. Nothing was uploaded or published. Previous clips and original footage remain preserved.','','The music is cleared instrumental material; no current trend claim is made.','']
(v.RELEASE/'DELIVERY_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
v.DEST.mkdir(exist_ok=True)
(v.DEST/'REVIEW_REPORT.md').write_text('# New Cairn batch of three\n\n[Clips, evidence and validation report](../../Releases/2026-11-15-batch-three/DELIVERY_REPORT.md).\n',encoding='utf-8')
snapshot=v.RELEASE/'source';snapshot.mkdir(exist_ok=True)
for f in HERE.iterdir():
    if f.is_file() and f.suffix in ('.py','.json','.md'):shutil.copy2(f,snapshot/f.name)
shutil.copytree(HERE/'tests',snapshot/'tests',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
(snapshot/'tools').mkdir(exist_ok=True)
for name in ('create_batch_three.py','create_visual_stories_v2.py','batch_three_speech.py','repair_batch_three_hand_layout.py','refine_batch_three_signage.py','prepare_batch_three_piton_script.py','record_hand_source_transition.py','check_batch_three_delivery.py','package_batch_three.py'):
    shutil.copy2(v.gs.ROOT/'tools'/name,snapshot/'tools'/name)
save(v.RELEASE/'source_manifest.json',{str(f.relative_to(snapshot)):digest(f) for f in snapshot.rglob('*') if f.is_file()})
print(v.RELEASE/'DELIVERY_REPORT.md')
