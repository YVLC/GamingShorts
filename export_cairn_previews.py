#!/usr/bin/env python3
"""Export selected Cairn gameplay preview windows without recompressing the full recording.
Reads a manifest beside this file. Does not touch project databases or original footage.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEFAULT_SOURCE=Path('/mnt/d/GamingShorts/Sources/videoplayback (2).mp4')
DEFAULT_MANIFEST=ROOT/'Cairn_90min_Review_Manifest.json'
DEFAULT_OUT=Path('/mnt/d/GamingShorts/ReviewExports/Cairn_FocusedPreviews')

def probe_duration(path):
 p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(f'ffprobe error: {p.stderr.strip()}')
 return float(p.stdout.strip())

def main():
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
 a.add_argument('--manifest',type=Path,default=DEFAULT_MANIFEST)
 a.add_argument('--output-dir',type=Path,default=DEFAULT_OUT)
 a.add_argument('--ids',help='Comma-separated preview IDs; default: all')
 a.add_argument('--list',action='store_true',help='List preview windows, no source or FFmpeg required')
 a.add_argument('--dry-run',action='store_true',help='Print FFmpeg requests; do not encode')
 a.add_argument('--force',action='store_true',help='Regenerate an existing preview (never source)')
 args=a.parse_args()
 manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
 windows=manifest['preview_windows']
 if args.ids:
  ids={x.strip() for x in args.ids.split(',') if x.strip()}
  unknown=ids-{w['id'] for w in windows}
  if unknown:a.error('Unknown preview ID(s): '+', '.join(sorted(unknown)))
  windows=[w for w in windows if w['id'] in ids]
 if args.list:
  for w in windows:print(f"{w['id']:24} {w['start']:7.1f}–{w['start']+w['duration']:<7.1f} sec  {w['label']}")
  return 0
 if not args.source.is_file():a.error('Recording not found: '+str(args.source))
 if not all(shutil.which(x) for x in ('ffmpeg','ffprobe')):a.error('ffmpeg and ffprobe required')
 d=probe_duration(args.source)
 for w in windows:
  if not (0<=w['start']<d and 0<w['duration'] and w['start']+w['duration']<=d+0.2):a.error('Window outside recording: '+w['id'])
 args.output_dir.mkdir(parents=True,exist_ok=True)
 result=[]
 for i,w in enumerate(windows,1):
  dest=args.output_dir/f"{w['id']}.mp4"
  if dest.is_file() and not args.force:
   try:
    v=probe_duration(dest)
    if abs(v-w['duration'])<1.5:
     print(f'[{i}/{len(windows)}] CACHED {dest.name} ({v:.1f}s)',flush=True)
     result.append(dest);continue
   except Exception:pass
  tmp=dest.with_suffix('.partial.mp4')
  cmd=['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y','-ss',str(w['start']),'-i',str(args.source),'-t',str(w['duration']),
       '-map','0:v:0','-map','0:a:0?','-vf','fps=12,scale=960:-2:flags=fast_bilinear',
       '-c:v','libx264','-preset','veryfast','-crf','31','-pix_fmt','yuv420p','-threads','2',
       '-c:a','aac','-b:a','64k','-ac','2','-movflags','+faststart','-sn','-dn',str(tmp)]
  print(f'[{i}/{len(windows)}] {w["id"]}: {w["start"]:.1f}–{w["start"]+w["duration"]:.1f} sec',flush=True)
  if args.dry_run:continue
  try:
   subprocess.run(cmd,check=True)
   v=probe_duration(tmp)
   if abs(v-w['duration'])>1.5:raise RuntimeError(f'Unexpected preview duration for {w["id"]}: {v:.1f}s')
   tmp.replace(dest)
  finally:
   if tmp.exists():tmp.unlink()
  result.append(dest)
 if args.dry_run:return 0
 output_zip=args.output_dir.parent/'Cairn_FocusedPreviews.zip'
 print('Packaging',len(result),'previews. Original source is untouched.',flush=True)
 with zipfile.ZipFile(output_zip,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
  z.write(args.manifest,arcname='Cairn_90min_Review_Manifest.json')
  for p in result:z.write(p,arcname=p.name)
 print('REVIEW ZIP:',output_zip,flush=True)
 print('Upload the review ZIP to ChatGPT. Nothing was uploaded or published automatically.',flush=True)
 return 0
if __name__=='__main__':
 try:sys.exit(main())
 except (RuntimeError,subprocess.CalledProcessError,FileNotFoundError,ValueError) as e:
  print('STOPPED SAFELY:',e,file=sys.stderr);sys.exit(1)
