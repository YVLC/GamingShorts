#!/usr/bin/env python3
"""Opt-in GamingShorts caption and quality upgrade for the NEXT TWO Shorts.
Default is verification only; --apply backs up and updates only two modules and config.
No source changes, Codex, HeyGen generation, deletion, or publishing.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,sys,tempfile,datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
SERVER=Path('/mnt/d/GamingShorts/Automation/gamingshorts_v2')
EXPECTED={'captions.py':'f42dcf554662c20987babd89039b216b6118c2af5fb6dd7695ae564c9c689655',
          'gaming_shorts.py':'bde45ea12fba030f7b70db872f1242c7058e37b8f6fe4a4c60e233d3a823b0e2'}
TARGET={'caption_mode':'karaoke','crf':18,'fps':60,'x264_preset':'medium'}
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def atomically_copy(src,dst):
 fd,tmp=tempfile.mkstemp(prefix=dst.name+'.',suffix='.installing',dir=dst.parent)
 try:
  with os.fdopen(fd,'wb') as f: f.write(src.read_bytes());f.flush();os.fsync(f.fileno())
  os.replace(tmp,dst)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true')
 args=ap.parse_args()
 if not (SERVER/'start.py').is_file() or not (SERVER/'config.json').is_file():sys.exit('STOP: GamingShorts server not found')
 cur={};change={}
 for name,base in EXPECTED.items():
  dest=SERVER/name;source=HERE/'patches'/name
  if not dest.is_file() or not source.is_file():sys.exit('STOP: missing module '+name)
  before=sha(dest);want=sha(source);cur[name]=before
  if before not in (base,want):sys.exit('STOP: '+name+' differs from tested 2.1.2a. Nothing changed. Ask for a compatible patch.')
  change[name]=before!=want
 cfg_path=SERVER/'config.json';cfg=json.loads(cfg_path.read_text(encoding='utf-8'))
 if cfg.get('voice_model','heygen-voice-1-turbo-free')!='heygen-voice-1-turbo-free':
  sys.exit('STOP: paid voice model detected')
 if cfg.get('voice_id','f49763c1a284420b8f25f16472d8738e')!='f49763c1a284420b8f25f16472d8738e':
  sys.exit('STOP: Garret voice differs; refusing to change it')
 print('Verified GamingShorts 2.1.2a modules and Garret FREE model')
 print('Module changes:',change)
 print('Current settings:',{k:cfg.get(k,'(default)') for k in TARGET})
 print('Requested settings:',TARGET)
 if not args.apply:
  print('DRY RUN. Use --apply to install (backups are mandatory).')
  return
 if not any(change.values()) and all(cfg.get(k)==v for k,v in TARGET.items()):
  print('ALREADY INSTALLED; no modifications needed');return
 # Existing server lock also used by the workflow. Never patch a running render.
 sys.path.insert(0,str(SERVER))
 from common import locked
 with locked(Path(cfg.get('root','/mnt/d/GamingShorts'))/'Database'/'.workflow_v2.lock'):
  backup=SERVER/'Backups'/('next_two_karaoke_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
  backup.mkdir(parents=True,exist_ok=False)
  for name in (*EXPECTED,'config.json'):shutil.copy2(SERVER/name,backup/name)
  (backup/'manifest.json').write_text(json.dumps({'original_sha256':{k:sha(backup/k) for k in (*EXPECTED,'config.json')},'quality_settings':TARGET},indent=2))
  try:
   for name,needed in change.items():
    if needed:atomically_copy(HERE/'patches'/name,SERVER/name)
   cfg.update(TARGET)
   fd,temp=tempfile.mkstemp(dir=SERVER,prefix='config.',suffix='.tmp')
   with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(cfg,f,indent=2,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
   os.replace(temp,cfg_path)
   assert all(sha(SERVER/k)==sha(HERE/'patches'/k) for k in EXPECTED)
   assert all(json.loads(cfg_path.read_text())[k]==v for k,v in TARGET.items())
  except Exception:
   for name in (*EXPECTED,'config.json'):atomically_copy(backup/name,SERVER/name)
   raise
  print('INSTALLED. Backup:',backup)
  print('Rendering: 1080x1920 60 FPS, CRF 18, x264 medium, Lanczos upscale, yellow real-word captions.')
  print('Existing Garret/Codex automation untouched. New renders still require your review.')
if __name__=='__main__':
 try:main()
 except Exception as e:sys.exit('STOP: '+str(e))
