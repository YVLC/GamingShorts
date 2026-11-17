"""Integrated renderer. No paid API, publication, or source-deletion code."""
from __future__ import annotations
import array, json, math, os, re, subprocess, textwrap, urllib.request, urllib.parse, wave
from pathlib import Path
from common import HERE, VERSION, config, digest, key, read, save, run, state
ROOT=Path(config()['root']).expanduser().resolve()
VOICE_ID=config()['voice_id']

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
 if doc.get('editorial',{}).get('policy')=='dialogue-editorial-v1':
  from dialogue_editorial import validate as dialogue_validate
  return dialogue_validate(doc,meta)
 import story_policy
 story_policy.validate(doc,story_policy.references(p))
 if not isinstance(clips,list) or not 3<=len(clips)<=10:raise ValueError('Use 3–10 clips')
 for i,c in enumerate(clips,1):
  if c.get('framing')=='tracked_cover':
   from render_sources import tracking_path
   tracking_path(c.get('tracking',[{'at':0,'x':.5}]),float(c['duration']))
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

def normalize_voice_exact(voice, output, seconds, cfg, log=None, gain_db=None):
 # ffmpeg loudnorm can drop 20–60 ms (or more) of samples when rate-changing
 # and cutting the stream with output -t. Normalize, reset PTS, then pad/trim
 # to the requested EXACT sample count rather than loosening QC tolerances.
 samples=round(float(seconds)*48000)
 if samples<=0:raise ValueError('Cannot normalize empty narration')
 normalizer=f'volume={gain_db:.9f}dB' if gain_db is not None else f'loudnorm=I={cfg["voice_lufs"]}:TP=-1.5:LRA=9'
 af=(normalizer+','
     f'aresample=48000,asetpts=N/SR/TB,'
     f'apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB')
 run(['ffmpeg','-v','error','-nostdin','-y','-i',voice,
      '-af',af,'-ar','48000','-ac','2','-c:a','pcm_f32le',output],logfile=log)
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
 cfg=config();m=read(Path(project)/'manifest.json');doc=read(Path(project)/'edit_plan.json')
 import music_library
 selected=music_library.select(project)
 return key({'renderer':VERSION,'code':digest(__file__),'plan':read(Path(project)/'edit_plan.json'),
 'quality_code':{name:digest(HERE/name) for name in ('quality_checks.py','audio_pipeline.py','render_sources.py','music_library.py','music_mix.py','music_segments.py','music_composer.py')},
 'source_bundle':m.get('source_bundle'),
 'story_policy':__import__('story_policy').receipt_identity(project,doc) if doc.get('editorial',{}).get('policy') in ('gaming-stories-v1','gaming-stories-v2') else None,
 'audio_master':digest(Path(voices[0]).parent.parent/'Audio/heygen_full.wav') if voices and (Path(voices[0]).parent.parent/'Audio/heygen_full.wav').exists() else None,
 'source':m.get('source_sha256'),'config':cfg,'music':selected.get('sha256'),'music_selection':selected,'captions_code':digest(HERE/'captions.py'),'alignment':digest(Path(voices[0]).parent.parent/'word_alignment.json') if voices and cfg.get('caption_mode')=='karaoke' and (Path(voices[0]).parent.parent/'word_alignment.json').exists() else None,'font':digest(cfg['font']),
 'audio':[digest(v) for v in voices],
 'voice_metadata':read(Path(voices[0]).parent.parent/'provenance.json') if voices and (Path(voices[0]).parent.parent/'provenance.json').exists() else None})

def completed(project):
 p=Path(project);q=p/'qc_report.json'
 if (p/'edit_plan.json').exists() and read(p/'edit_plan.json').get('editorial',{}).get('policy')=='dialogue-editorial-v1':
  from dialogue_editorial import completed as dialogue_completed
  return dialogue_completed(p)
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
 if doc.get('editorial',{}).get('policy') in ('gaming-stories-v1','gaming-stories-v2'):
  if m.get('full_game'):
   from game_plan import guard
   guard(p,doc)
  else:
   from story_policy import require_review
   require_review(p,doc)
 import render_sources, audio_pipeline, quality_checks
 resolved=[render_sources.resolve(m,c,probe) for c in clips]
 intro=doc.get('opening_action')
 intro_source=render_sources.resolve(m,intro,probe) if intro else None
 if intro and not .25<=float(intro['duration'])<=2:raise ValueError('Opening action must be a brief .25-2 seconds')
 all_sources=resolved+([intro_source] if intro_source else [])
 print('Verifying original source checksums (review proxies are never production inputs)...',flush=True)
 checked=set()
 for source in all_sources:
  if str(source['path']) in checked:continue
  if not source['path'].is_file() or digest(source['path'])!=source['sha256']:raise RuntimeError('Original source missing or changed')
  checked.add(str(source['path']))
 voices=[Path(voice_folder)/'Voices'/f'line_{i:02d}.wav' for i in range(1,len(clips)+1)]
 prov=read(Path(voice_folder)/'provenance.json')
 for v in voices:
  if not v.exists() or digest(v)!=prov['files'].get(v.name):raise RuntimeError('Voice provenance mismatch')
 import captions, music_library
 alignment=captions.load(voice_folder,clips) if cfg.get('caption_mode')=='karaoke' else None
 selected_music=music_library.select(p)
 fp=render_fingerprint(p,voices)
 if completed(p):return Path(read(p/'qc_report.json')['output'])
 out=p/'Renders'/fp[:16];out.mkdir(parents=True,exist_ok=True);log=out/'ffmpeg.log';w=cfg['width'];h=cfg['height']
 fps=render_sources.delivery_rate(all_sources,cfg['fps'])
 # Relative caption/font filenames avoid FFmpeg filter path quoting bugs on spaces/colon.
 import shutil
 shutil.copyfile(cfg['font'],out/'font.ttf')
 durations=[];offset=0;windows=[];filters=[];normalized=[];placements=[];caption_warnings=[];audio_diagnostics=[];visual_reports=[]
 timing=read(Path(voice_folder)/'voice_timing.json') if (Path(voice_folder)/'voice_timing.json').exists() else None
 master=Path(voice_folder)/'Audio/heygen_full.wav'
 if not master.exists():
  import numpy as np
  master=out/'normalization_reference.wav'
  if not master.exists():audio_pipeline.export_segment(np.concatenate([audio_pipeline.read_audio(v) for v in voices]),master)
 gain_profile=audio_pipeline.master_gain(master,cfg['voice_lufs'])
 save(out/'audio_master_gain.json',gain_profile)
 if timing and (Path(voice_folder)/'Audio/heygen_full.wav').exists():
  master_samples=audio_pipeline.read_audio(master)
  boundary_report=[{'cut':cut,'dbfs':audio_pipeline.boundary_level(master_samples,round(cut*48000))} for cut in timing['segment_boundaries'][1:-1]]
  if any(row['dbfs']>-45 for row in boundary_report):raise RuntimeError('Narration cut crosses audible speech; create an existing-master boundary revision before rendering')
 else:boundary_report=[]
 if intro:
  graph,framing=render_sources.picture_filters(intro_source,cfg,intro.get('framing','auto'))
  graph='setpts=PTS-STARTPTS,'+graph
  if intro_source['fps']>fps:graph+=f',fps={fps}'
  shot,visual=render_sources.encode_shot(p,out,0,intro_source,cfg,graph+',format=yuv420p',fps,framing,run,probe,duration)
  visual['final_start']=0.;visual_reports.append(visual);offset=float(intro['duration'])
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
  source=dict(resolved[i-1],tracking=c.get('tracking',[{'at':0,'x':.5}]),caption_y=c.get('caption_y',cfg.get('caption_y',.69)),trim_top=c.get('trim_top',0),trim_bottom=c.get('trim_bottom',0))
  picture,framing=render_sources.picture_filters(source,cfg,c.get('framing','auto'))
  vf=['setpts=PTS-STARTPTS',picture]
  if source['fps']>fps:vf.append(f'fps={fps}')
  def draw(text,prefix,enable):
   for j,line in enumerate(caption_lines(text)):
    name=f'{prefix}_{j}.txt';(out/name).write_text(line)
    size=max(12,min(round(w*.052),int(w*.82/(max(1,len(line))*1.1))));y=round(h*.72)+j*round(h*.04)
    vf.append(f"drawtext=fontfile=font.ttf:textfile={name}:expansion=none:fontsize={size}:fontcolor=white:borderw={max(1,round(w/270))}:bordercolor=black:x=(w-text_w)/2:y={y}:enable='{enable}'")
  if alignment:
   words=alignment['lines'][i-1]['words'];captions.write_ass(out/f'karaoke_{i:02d}.ass',words,w,h,delay,position_y=c.get('caption_y',cfg.get('caption_y',.69)))
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
  shot,visual=render_sources.encode_shot(p,out,i,source,cfg,','.join(vf),fps,framing,run,probe,duration)
  visual['final_start']=offset;visual_reports.append(visual)
  # Materialize normalization separately: some FFmpeg builds mishandle multiple
  # loudnorm branches feeding delayed amix inputs (truncation/timebase issues).
  nv=out/f'normalized_{i:02d}.wav'
  normalize_voice_exact(v,nv,spoken,cfg,log,gain_db=gain_profile['gain_db'])
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
 (out/'concat.txt').write_text(''.join(f"file 'shot_{i:02d}.mp4'\n" for i in range(0 if intro else 1,len(clips)+1)))
 video=out/'video.mp4';run(['ffmpeg','-v','error','-nostdin','-y','-f','concat','-safe','0','-i',out/'concat.txt','-c','copy',video],logfile=log)
 inputs=[]
 for v in normalized:inputs+=['-i',v]
 # Duration-based output -t intermittently drops the final 100 ms on this FFmpeg
 # build. Finish the mix at an exact sample count, as for normalized narration.
 samples=round(offset*48000)
 filters.append(''.join(f'[v{i}]' for i in range(1,len(clips)+1))+f'amix=inputs={len(clips)}:normalize=0,aresample=48000,apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB[speech]')
 speech=out/'speech.wav';run(['ffmpeg','-v','error','-nostdin','-y',*inputs,'-filter_complex',';'.join(filters),'-map','[speech]','-ar','48000','-c:a','pcm_f32le','-fs','64000000',speech],logfile=log)
 if abs(duration(speech)-offset)>.05:raise RuntimeError('Speech stem duration failed validation')
 import music_mix
 gameplay=music_mix.gameplay_stem(([intro_source] if intro_source else [])+resolved,out,offset,cfg,run,probe,log)
 mix_master,speech,bed,mix_report=music_mix.mix(speech,selected_music,offset,out,cfg,run,cuts=[v['final_start'] for v in visual_reports if v['final_start']>0],gameplay=gameplay,log=log)
 candidate=out/'candidate.mp4'
 run(['ffmpeg','-v','error','-nostdin','-y','-i',video,'-i',mix_master,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',offset,'-movflags','+faststart',candidate],logfile=log)
 if alignment:caption_warnings+=captions.sidecars(out,alignment['lines'],placements)
 print('Validating final video and mixed narration...',flush=True)
 report=qc(candidate,speech,bed,windows,offset,out,cfg)
 for visual in visual_reports:
  final_profile=quality_checks.measure_cadence(candidate,visual['final_start'],visual.get('cadence_sample_seconds',min(3.,visual['duration'])),fps,roi=visual['output_roi'])
  expected=dict(visual['source_cadence'])
  if expected.get('active_updates_per_second'):expected['active_updates_per_second']=min(float(fps),expected['active_updates_per_second'])
  comparison=quality_checks.compare_cadence(expected,final_profile)
  visual['final_cadence']=final_profile;visual['final_comparison']=comparison
  if comparison['error']:report['errors'].append(comparison['error'])
  if expected.get('cadence_limited'):report['warnings'].append('Original capture is cadence-limited; output cannot invent missing motion frames')
 report['visual_quality']={'delivery_rate':str(fps),'requested_cap':cfg['fps'],'scenes':visual_reports,'proxy_rendering':False,'source_mapping':m.get('source_bundle')}
 report['narration_master_gain']=gain_profile;report['narration_boundaries']=boundary_report
 report['mix_master']=str(mix_master)
 if report['errors']:report['status']='failed'
 report['warnings']+=caption_warnings
 report['audio_artifact_indicators']=audio_diagnostics
 from audio_checks import indicators
 report['final_audio_artifact_indicators']=indicators(pcm(candidate,out/'artifact_mix.wav'))
 for row in audio_diagnostics:
  if row['original']['possible_impulse_seconds'] or row['normalized']['possible_impulse_seconds'] or row['normalized']['longest_clipped_run']>=3:report['warnings'].append(f"Line {row['line']}: possible audio artifact; compare saved original and normalized WAVs")
 report['captions']={'mode':cfg.get('caption_mode','phrase'),'timing_validation':'word intervals checked against saved audio duration and exact script' if alignment else 'phrase captions; no word synchronization','listening_review':'not_performed'}
 report['music']=selected_music
 report['audio_mix']=mix_report
 encoded_loudness=audio_pipeline.master_gain(candidate,mix_report['settings']['target_lufs'],mix_report['settings']['true_peak_db'])
 report['encoded_audio_loudness']=encoded_loudness
 if encoded_loudness['input_true_peak_db']>-.9:
  report['errors'].append('Encoded mix exceeds -0.9 dBTP');report['status']='failed' 
 report.update({'input_key':fp,'version':VERSION,'cta_timing':'word_timestamp' if prov.get('cta_offset_seconds') is not None else 'approximate_last_1.7_seconds','editorial_review':'required'})
 if report['status']!='technical_pass':
  save(out/'qc_report.json',report);state(p,'qc_failed',report=str(out/'qc_report.json'));raise RuntimeError(f'Final QC failed: {report["errors"]}')
 final=ROOT/'ReadyForReview'/(p.name+'_v2_'+fp[:8]+'.mp4');final.parent.mkdir(parents=True,exist_ok=True)
 tmp=final.with_suffix('.partial.mp4');shutil.copyfile(candidate,tmp);os.replace(tmp,final)
 report.update(output=str(final),output_sha256=digest(final));save(out/'qc_report.json',report);save(p/'qc_report.json',report);state(p,'validated',output=str(final))
 if alignment:
  for name in ('subtitles.srt','caption_timeline.json'):shutil.copyfile(out/name,final.with_suffix('.srt' if name.endswith('.srt') else '.captions.json'))
 (final.with_suffix('.music.txt')).write_text(selected_music.get('attribution','')+'\n')
 music_library.commit(p,selected_music,final,fp,mix_report['settings'],performance=report)
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
