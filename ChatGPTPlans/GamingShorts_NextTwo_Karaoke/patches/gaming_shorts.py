"""Integrated renderer. No paid API, publication, or source-deletion code."""
from __future__ import annotations
import array, json, math, os, re, subprocess, textwrap, urllib.request, urllib.parse, wave
from pathlib import Path
from common import HERE, VERSION, config, digest, key, read, save, run, state
ROOT=Path(config()['root']).expanduser().resolve()
VOICE_ID=config()['voice_id']
# Audio-only hotfix: leave the verified visual-video cache identity intact.
# This is the SHA256 of gaming_shorts.py from GamingShorts 2.1.2 before the
# normalization-only change; it is intentionally limited to this exact baseline.
VISUAL_CACHE_SIGNATURE='149c5301a2a3a20b4e2ff6b88a454ceccf5f7653f56165db9c64438b6faf3772'

def probe(path):
 p=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,text=True,check=True,timeout=60)
 return json.loads(p.stdout)
def duration(path):return float(probe(path)['format']['duration'])
def download(url,path):
 def valid(u):
  p=urllib.parse.urlparse(u);h=(p.hostname or '').lower()
  return p.scheme=='https' and any(h==d or h.endswith('.'+d) for d in ('heygen.com','heygen.ai'))
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   if not valid(newurl):raise ValueError('Unrecognized audio redirect domain; download stopped.')
   return super().redirect_request(req,fp,code,msg,headers,newurl)
 if not valid(url):raise ValueError('Unrecognized audio URL')
 with urllib.request.build_opener(Redirect).open(url,timeout=180) as r:
  data=r.read(35*1024*1024+1)
  if len(data)>35*1024*1024:raise ValueError('Audio download exceeds limit')
  Path(path).write_bytes(data)
def validate(project):
 p=Path(project);doc=read(p/'edit_plan.json');meta=read(p/'manifest.json');clips=doc.get('clips');cfg=config()
 if not isinstance(clips,list) or not 3<=len(clips)<=10:raise ValueError('Use 3–10 clips')
 for i,c in enumerate(clips,1):
  a=float(c['start']);d=float(c['duration'])
  if not all(map(math.isfinite,[a,d])) or a<0 or not 2<=d<=12 or a+d>float(meta['duration'])+.02:raise ValueError(f'Invalid source timing in clip {i}')
  for f,limit in [('narration',200),('caption',90)]:
   if not isinstance(c.get(f),str) or not c[f].strip() or len(c[f])>limit:raise ValueError(f'Invalid {f}, clip {i}')
  caption_lines(c['caption'])
 total=sum(float(c['duration']) for c in clips)
 if not cfg['min_seconds']<=total<=cfg['max_seconds']:raise ValueError(f'Total {total:.2f}s outside configured range')
 return doc

def caption_lines(s):
 s=' '.join(s.upper().split())
 # Latin text with ordinary punctuation; avoids accidental emoji/missing-glyph boxes.
 s=re.sub(r'[^\x20-\x7e]','',s)
 if not s:raise ValueError('Caption needs displayable English text')
 lines=textwrap.wrap(s,width=22,break_long_words=True,break_on_hyphens=False)
 if len(lines)>3:raise ValueError('Caption exceeds three lines; shorten it')
 return lines

def normalize_voice_exact(voice, output, seconds, cfg, log=None):
 # ffmpeg loudnorm can drop 20–60 ms (or more) of samples when rate-changing
 # and cutting the stream with output -t. Normalize, reset PTS, then pad/trim
 # to the requested EXACT sample count rather than loosening QC tolerances.
 samples=round(float(seconds)*48000)
 if samples<=0:raise ValueError('Cannot normalize empty narration')
 af=(f'loudnorm=I={cfg["voice_lufs"]}:TP=-1.5:LRA=9,'
     f'aresample=48000,asetpts=N/SR/TB,'
     f'apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB')
 run(['ffmpeg','-v','error','-nostdin','-y','-i',voice,
      '-af',af,'-ar','48000','-ac','2',output],logfile=log)
 measured=duration(output)
 if abs(measured-seconds)>.05:
  raise RuntimeError(f'Normalized narration duration changed: {seconds:.5f}s -> {measured:.5f}s')
 return measured

def pcm(path, out):
 run(['ffmpeg','-v','error','-nostdin','-y','-i',path,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',out])
 with wave.open(str(out),'rb') as w:
  a=array.array('h');a.frombytes(w.readframes(w.getnframes()))
  if os.sys.byteorder!='little':a.byteswap()
 return a

def rms(a):return math.sqrt(sum(float(x)*x for x in a)/max(1,len(a)))
def db(a):return 20*math.log10(max(rms(a),.01)/32768)
def correlation(a,b):
 n=min(len(a),len(b))
 if n<100:return 0
 a=a[:n];b=b[:n];ab=sum(float(x)*y for x,y in zip(a,b));den=math.sqrt(sum(float(x)*x for x in a)*sum(float(y)*y for y in b))
 return ab/den if den else 0

def render_fingerprint(project, voices):
 cfg=config();m=read(Path(project)/'manifest.json')
 import music_library
 selected=music_library.select(project);music=Path(selected['path'])
 return key({'renderer':VERSION,'code':digest(__file__),'plan':read(Path(project)/'edit_plan.json'),
 'source':m.get('source_sha256'),'config':cfg,'music':digest(music),'music_selection':selected,'captions_code':digest(HERE/'captions.py'),'alignment':digest(Path(voices[0]).parent.parent/'word_alignment.json') if voices and cfg.get('caption_mode')=='karaoke' and (Path(voices[0]).parent.parent/'word_alignment.json').exists() else None,'font':digest(cfg['font']),
 'audio':[digest(v) for v in voices],
 'voice_metadata':read(Path(voices[0]).parent.parent/'provenance.json') if voices and (Path(voices[0]).parent.parent/'provenance.json').exists() else None})

def completed(project):
 p=Path(project);q=p/'qc_report.json'
 if not q.exists():return False
 try:
  report=read(q);v=read(p/'active_voice.json');folder=p/v['folder'];meta=read(folder/'provenance.json')
  voices=[folder/'Voices'/x for x in meta['files']]
  current=key({'lines':[c['narration'].strip() for c in validate(p)['clips']], 'voice_id':config()['voice_id'],'model':config()['voice_model'],'expressivenessBoost':1.0,'language':'en'})
  if current!=meta['request_key']:return False
  final=Path(report['output'])
  return report['status']=='technical_pass' and final.is_file() and digest(final)==report['output_sha256'] and report['input_key']==render_fingerprint(p,voices)
 except (OSError,ValueError,KeyError,TypeError):return False

def render(project, voice_folder):
 p=Path(project);cfg=config();doc=validate(p);m=read(p/'manifest.json');src=Path(m['source']);clips=doc['clips']
 print('Verifying source recording checksum (large recordings can take several minutes)...',flush=True)
 if not src.is_file() or digest(src)!=m.get('source_sha256'):raise RuntimeError('Source missing or changed. Restore the original source.')
 voices=[Path(voice_folder)/'Voices'/f'line_{i:02d}.wav' for i in range(1,len(clips)+1)]
 prov=read(Path(voice_folder)/'provenance.json')
 for v in voices:
  if not v.exists() or digest(v)!=prov['files'].get(v.name):raise RuntimeError('Voice provenance mismatch')
 import captions, music_library
 alignment=captions.load(voice_folder,clips) if cfg.get('caption_mode')=='karaoke' else None
 selected_music=music_library.select(p)
 fp=render_fingerprint(p,voices)
 if completed(p):return Path(read(p/'qc_report.json')['output'])
 out=p/'Renders'/fp[:16];out.mkdir(parents=True,exist_ok=True);log=out/'ffmpeg.log';w=cfg['width'];h=cfg['height'];fps=cfg['fps']
 # Relative caption/font filenames avoid FFmpeg filter path quoting bugs on spaces/colon.
 import shutil
 shutil.copyfile(cfg['font'],out/'font.ttf')
 durations=[];offset=0;windows=[];filters=[];normalized=[];placements=[];caption_warnings=[];audio_diagnostics=[]
 timing=read(Path(voice_folder)/'voice_timing.json') if (Path(voice_folder)/'voice_timing.json').exists() else None
 for i,(c,v) in enumerate(zip(clips,voices),1):
  print(f'Rendering clip {i}/{len(clips)}...',flush=True)
  sec=float(c['duration']);spoken=duration(v);durations.append(sec)
  if spoken>sec-.15:raise RuntimeError(f'Voice {i} ({spoken:.2f}s) does not fit scene ({sec:.2f}s). Extend this scene or shorten its text.')
  signal=pcm(v,out/f'check_{i}.wav')
  if db(signal)<-45:raise RuntimeError(f'Voice {i} is effectively silent')
  delay=max(.05,sec-spoken-.10) if i==len(clips) else min(.15,max(.05,(sec-spoken)/2))
  # Use actual CTA word onset when supplied; otherwise explicitly report approximation.
  cta=prov.get('cta_offset_seconds')
  switch=delay+cta if i==len(clips) and cta is not None else max(0,sec-1.7)
  switch=max(0,min(sec-.1,switch))
  vf=[f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos',f'crop={w}:{h}','setsar=1',f'fps={fps}']
  def draw(text,prefix,enable):
   for j,line in enumerate(caption_lines(text)):
    name=f'{prefix}_{j}.txt';(out/name).write_text(line)
    size=max(12,min(round(w*.052),int(w*.82/(max(1,len(line))*1.1))));y=round(h*.72)+j*round(h*.04)
    vf.append(f"drawtext=fontfile=font.ttf:textfile={name}:expansion=none:fontsize={size}:fontcolor=white:borderw={max(1,round(w/270))}:bordercolor=black:x=(w-text_w)/2:y={y}:enable='{enable}'")
  if alignment:
   words=alignment['lines'][i-1]['words'];captions.write_ass(out/f'karaoke_{i:02d}.ass',words,w,h,delay)
   vf.append(f"ass=karaoke_{i:02d}.ass:fontsdir=.")
   if i==len(clips):
    cta_words=[word for word in words if 'subscribe' in captions.tokens(word['word'])]
    if cta_words and delay+cta_words[-1]['start']<sec-2:
     caption_warnings.append('Spoken CTA starts before final two seconds. Existing narration preserved; timing needs review.')
  else:
   draw(c['caption'],f'caption_{i}',f'lt(t,{switch:.4f})' if i==len(clips) else '1')
   if i==len(clips):draw('SUBSCRIBE FOR MORE',f'cta_{i}',f'gte(t,{switch:.4f})')
  placements.append(offset+delay)
  vf.append('format=yuv420p');shot=out/f'shot_{i:02d}.mp4'
  # Visual-only cache: mix changes never force another video encode.
  shotkey=key({'code':VISUAL_CACHE_SIGNATURE,'source':m['source_sha256'],'start':c['start'],'duration':sec,'filter':vf,
   'caption':c['caption'],'words':alignment['lines'][i-1] if alignment else None,'font':digest(cfg['font']),
   'width':w,'height':h,'fps':fps,'crf':cfg['crf'],'encoder':cfg.get('encoder','libx264'), 'x264_preset':cfg.get('x264_preset','medium')})
  cache=p/'VideoCache'/shotkey;cache.mkdir(parents=True,exist_ok=True);cached=cache/'shot.mp4';proof=cache/'proof.json'
  reusable=False
  if cached.exists() and proof.exists():
   try:reusable=digest(cached)==read(proof)['sha256'] and abs(duration(cached)-sec)<.1
   except (ValueError,KeyError,OSError,subprocess.SubprocessError):pass
  if reusable:
   print(f'Reusing encoded clip {i}/{len(clips)}',flush=True);shutil.copyfile(cached,shot)
  else:
   encoder=cfg.get('encoder','libx264')
   if encoder not in ('libx264','h264_qsv'):raise ValueError('Unsupported encoder')
   encargs=['-threads','2','-preset',cfg.get('x264_preset','medium'),'-crf',cfg['crf']] if encoder=='libx264' else ['-preset','veryfast','-global_quality',cfg.get('qsv_quality',22)]
   run(['ffmpeg','-v','error','-nostdin','-y','-ss',c['start'],'-i',src,'-t',sec,'-an','-vf',','.join(vf),'-c:v',encoder,*encargs,'-pix_fmt','yuv420p',shot],cwd=out,logfile=log)
   run(['ffmpeg','-v','error','-xerror','-i',shot,'-f','null','-'],logfile=log)
   temp=cache/'shot.partial.mp4';shutil.copyfile(shot,temp);os.replace(temp,cached);save(proof,{'sha256':digest(cached)})
  # Materialize normalization separately: some FFmpeg builds mishandle multiple
  # loudnorm branches feeding delayed amix inputs (truncation/timebase issues).
  nv=out/f'normalized_{i:02d}.wav'
  normalize_voice_exact(v,nv,spoken,cfg,log)
  from audio_checks import indicators
  original_check=indicators(signal);normalized_check=indicators(pcm(nv,out/f'normalized_check_{i}.wav'))
  audio_diagnostics.append({'line':i,'original':original_check,'normalized':normalized_check})
  normalized.append(nv)
  filters.append(f'[{i-1}:a]adelay={round((offset+delay)*1000)}:all=1[v{i}]')
  lo,hi=0,spoken
  if timing:
   lo=timing['source_word_spans'][i-1][0]-timing['segment_boundaries'][i-1]
   hi=timing['source_word_spans'][i-1][1]-timing['segment_boundaries'][i-1]
  windows.append([offset+delay+lo,offset+delay+hi]);offset+=sec
 (out/'concat.txt').write_text(''.join(f"file 'shot_{i:02d}.mp4'\n" for i in range(1,len(clips)+1)))
 video=out/'video.mp4';run(['ffmpeg','-v','error','-nostdin','-y','-f','concat','-safe','0','-i',out/'concat.txt','-c','copy',video],logfile=log)
 inputs=[]
 for v in normalized:inputs+=['-i',v]
 filters.append(''.join(f'[v{i}]' for i in range(1,len(clips)+1))+f'amix=inputs={len(clips)}:normalize=0,apad=whole_dur={offset},atrim=duration={offset},asetpts=N/SR/TB[speech]')
 speech=out/'speech.wav';run(['ffmpeg','-v','error','-nostdin','-y',*inputs,'-filter_complex',';'.join(filters),'-map','[speech]','-t',offset,'-ar','48000','-fs','64000000',speech],logfile=log)
 if abs(duration(speech)-offset)>.05:raise RuntimeError('Speech stem duration failed validation')
 music=Path(selected_music['path'])
 bed=out/'music.wav';run(['ffmpeg','-v','error','-nostdin','-y','-stream_loop','-1','-i',music,'-t',offset,'-af',f'loudnorm=I={cfg["music_lufs"]}:TP=-3:LRA=9','-ar','48000','-ac','2',bed],logfile=log)
 candidate=out/'candidate.mp4'
 run(['ffmpeg','-v','error','-nostdin','-y','-i',video,'-i',speech,'-i',bed,'-filter_complex','[1:a][2:a]amix=inputs=2:normalize=0,alimiter=limit=0.95:level=0:latency=1[a]','-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-t',offset,'-movflags','+faststart',candidate],logfile=log)
 if alignment:caption_warnings+=captions.sidecars(out,alignment['lines'],placements)
 print('Validating final video and mixed narration...',flush=True)
 report=qc(candidate,speech,bed,windows,offset,out,cfg)
 report['warnings']+=caption_warnings
 report['audio_artifact_indicators']=audio_diagnostics
 from audio_checks import indicators
 report['final_audio_artifact_indicators']=indicators(pcm(candidate,out/'artifact_mix.wav'))
 for row in audio_diagnostics:
  if row['original']['possible_impulse_seconds'] or row['normalized']['possible_impulse_seconds'] or row['normalized']['longest_clipped_run']>=3:report['warnings'].append(f"Line {row['line']}: possible audio artifact; compare saved original and normalized WAVs")
 report['captions']={'mode':cfg.get('caption_mode','phrase'),'timing_validation':'word intervals checked against saved audio duration and exact script' if alignment else 'phrase captions; no word synchronization','listening_review':'not_performed'}
 report['music']=selected_music
 report.update({'input_key':fp,'version':VERSION,'cta_timing':'word_timestamp' if prov.get('cta_offset_seconds') is not None else 'approximate_last_1.7_seconds','editorial_review':'required'})
 if report['status']!='technical_pass':
  save(out/'qc_report.json',report);state(p,'qc_failed',report=str(out/'qc_report.json'));raise RuntimeError(f'Final QC failed: {report["errors"]}')
 final=ROOT/'ReadyForReview'/(p.name+'_v2_'+fp[:8]+'.mp4');final.parent.mkdir(parents=True,exist_ok=True)
 tmp=final.with_suffix('.partial.mp4');shutil.copyfile(candidate,tmp);os.replace(tmp,final)
 report.update(output=str(final),output_sha256=digest(final));save(out/'qc_report.json',report);save(p/'qc_report.json',report);state(p,'validated',output=str(final))
 if alignment:
  for name in ('subtitles.srt','caption_timeline.json'):shutil.copyfile(out/name,final.with_suffix('.srt' if name.endswith('.srt') else '.captions.json'))
 (final.with_suffix('.music.txt')).write_text(selected_music.get('attribution','')+'\n')
 return final

def qc(final,speech,music,windows,expected,out,cfg):
 errors=[];warnings=[];media=probe(final);vs=[s for s in media['streams'] if s['codec_type']=='video'];a=[s for s in media['streams'] if s['codec_type']=='audio']
 if not vs or (vs[0]['width'],vs[0]['height'])!=(cfg['width'],cfg['height']) or not a:errors.append('Wrong dimensions or missing audio')
 if abs(float(media['format']['duration'])-expected)>.25:errors.append('Duration mismatch')
 dec=subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(final),'-f','null','-'],capture_output=True,text=True,timeout=cfg['media_timeout_seconds'])
 if dec.returncode:errors.append('Final file cannot fully decode')
 ref=pcm(speech,out/'qc_speech.wav');bed=pcm(music,out/'qc_music.wav');mixed=pcm(final,out/'qc_mix.wav');checks=[]
 for i,(start,end) in enumerate(windows,1):
  lo=int(start*16000);hi=int(end*16000);r=ref[lo:hi];b=bed[lo:hi];f=mixed[lo:hi];corr=correlation(r,f);margin=db(r)-db(b)
  checks.append({'line':i,'speech_dbfs':db(r),'voice_over_music_db':margin,'mix_correlation':corr})
  if db(r)<-45 or db(f)<-45:errors.append(f'Line {i}: silent speech window')
  if margin<8:errors.append(f'Line {i}: music too loud relative to speech')
  if corr<.50:errors.append(f'Line {i}: final audio does not sufficiently match speech stem')
 diag=subprocess.run(['ffmpeg','-hide_banner','-i',str(final),'-vf','blackdetect=d=0.5:pix_th=0.1,freezedetect=n=-50dB:d=2','-an','-f','null','-'],capture_output=True,text=True,timeout=cfg['media_timeout_seconds'])
 for line in diag.stderr.splitlines():
  if 'black_start:' in line or 'freeze_start:' in line:warnings.append(line.strip())
 if diag.returncode:errors.append('Visual diagnostic decode failed')
 run(['ffmpeg','-v','error','-nostdin','-y','-i',final,'-vf',f'fps=8/{expected},scale=180:320,tile=4x2','-frames:v','1',out/'review_sheet.jpg'])
 return {'status':'technical_pass' if not errors else 'failed','errors':errors,'warnings':warnings,'audio_windows':checks,'expected_duration':expected,'actual_duration':float(media['format']['duration']),'review_sheet':str(out/'review_sheet.jpg'),'limitations':'Correlation/RMS checks do not establish intelligibility, transcript accuracy, narrative quality, or visual crop quality. Watch and listen before approval.'}
