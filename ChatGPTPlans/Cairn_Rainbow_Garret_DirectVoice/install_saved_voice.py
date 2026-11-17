#!/usr/bin/env python3
"""Safely inject previously generated, authenticated FREE HeyGen timing into an imported Cairn project.
No synthesis, Codex, FFmpeg or publication here. Requires --apply to write."""
from pathlib import Path
import argparse, hashlib, json, math, sys
HERE=Path(__file__).resolve().parent
ROOT=Path('/mnt/d/GamingShorts')
SERVER=ROOT/'Automation'/'gamingshorts_v2'
PROJECT=ROOT/'Projects'/'V2'/'videoplayback_2_c8aec7b5_chatgpt_rainbow_v1'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply',action='store_true',help='write the one saved FREE voice result; otherwise read-only validation')
    args=ap.parse_args()
    if not SERVER.is_dir() or not (SERVER/'common.py').is_file():sys.exit('STOP: GamingShorts 2.1.x server not found')
    sys.path.insert(0,str(SERVER))
    from common import config,key,read,save
    from voices import request
    import gaming_shorts as gs
    if not (PROJECT/'manifest.json').is_file() or not (PROJECT/'edit_plan.json').is_file():
        sys.exit('STOP: Imported rainbow project absent; import rainbow_v1 first')
    doc=gs.validate(PROJECT)
    expected=read(HERE/'expected_narration.json')
    actual=[c['narration'].strip() for c in doc['clips']]
    if actual!=expected:sys.exit('STOP: Narration differs from the approved recording; no files changed')
    r=read(HERE/'voice_result.json'); cfg=config(); req=request(doc['clips'])
    if r['voice_id']!=cfg['voice_id'] or r['model']!=cfg['voice_model'] or r['model']!='heygen-voice-1-turbo-free':
        sys.exit('STOP: Your voice or free-model configuration differs; no files changed')
    if len(r['phrases'])!=len(doc['clips']):sys.exit('STOP: number of phrases does not match')
    dur=float(r['duration_seconds']); spans=[]; prev_end=-1.
    for i,(phrase,c) in enumerate(zip(r['phrases'],doc['clips']),1):
        a=float(phrase['first_word_start']);b=float(phrase['last_word_end'])
        if phrase.get('index')!=i or not (0<=a<b<=dur+.02) or a<prev_end:
            sys.exit(f'STOP: invalid speech timing at phrase {i}')
        spans.append((a,b));prev_end=b
    cuts=[0.]+[(spans[i][1]+spans[i+1][0])/2 for i in range(len(spans)-1)]+[dur]
    for i,c in enumerate(doc['clips']):
        chunk=cuts[i+1]-cuts[i]
        if chunk>float(c['duration'])-.2:sys.exit(f'STOP: voice phrase {i+1} would not fit its scene')
    keyid=key(req)
    dest_dir=PROJECT/'VoiceVersions'/keyid
    dest=dest_dir/'voice_result.json'
    if (dest_dir/'voice_generation_attempted.json').exists() and not dest.is_file():
        sys.exit('STOP: previous speech attempt marker exists. Investigate before installing.')
    if dest.exists():
        if read(dest)==r:print('ALREADY INSTALLED: matching free speech result');return
        sys.exit('STOP: another speech result exists; refusing to overwrite')
    if (dest_dir/'provenance.json').exists() or (dest_dir/'Audio'/'heygen_full.wav').exists():
        sys.exit('STOP: existing speech/audio found without matching result; refusing to overwrite')
    print('Verified imported project:',PROJECT)
    print('Verified active voice: Garret — Bold & Persuasive')
    print('Verified FREE model, actual phrase boundaries and CTA timestamp')
    for i,(c,span) in enumerate(zip(doc['clips'],spans),1):
        print(f'  {i}: narration {span[0]:.3f}–{span[1]:.3f}s; allocated scene {float(c["duration"]):.2f}s')
    if not args.apply:
        print('READ-ONLY preview. Rerun with --apply to install saved timing data. No HeyGen/Codex call.')
        return
    dest_dir.mkdir(parents=True,exist_ok=True)
    save(dest,r)
    print('INSTALLED:',dest)
    print('Next: python3 start.py --project "'+str(PROJECT)+'" --stop-after voice')
    print('That will download the existing Garret WAV and split it; no new generation request.')

if __name__=='__main__':
    try:main()
    except Exception as e:sys.exit('STOP: '+str(e))
