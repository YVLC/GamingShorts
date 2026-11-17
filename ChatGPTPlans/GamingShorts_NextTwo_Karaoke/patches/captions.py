"""Audio-derived word alignment and stable-position yellow word highlights.
No speech synthesis. Alignment estimates require a listening review.
"""
from pathlib import Path
import math, re, subprocess, sys
from common import HERE, config, digest, key, read, save

def tokens(text):return re.findall(r"[\w]+(?:['’][\w]+)*",text.lower())
def validate_words(words, text, seconds):
 if not words:raise ValueError('No word timing: refusing estimated karaoke')
 if tokens(' '.join(w['word'] for w in words))!=tokens(text):raise ValueError('Aligned words do not match narration text')
 last=0
 for w in words:
  a,b=float(w['start']),float(w['end'])
  if not math.isfinite(a+b) or a<last-.001 or b<=a or b>seconds+.02:raise ValueError('Invalid, overlapping, or out-of-audio word timing')
  if b-a>2.5:raise ValueError('Uncertain alignment: a word lasts over 2.5 seconds; review timing')
  last=b
 return words

def identity(folder,clips):
 return key({'code':digest(__file__),'worker':digest(HERE/'align_worker.py'),'model':config()['alignment_model'],
 'lines':[{'text':c['narration'],'sha256':digest(Path(folder)/'Voices'/f'line_{i:02d}.wav')} for i,c in enumerate(clips,1)]})

def load(folder, clips):
 import gaming_shorts as gs
 path=Path(folder)/'word_alignment.json'
 if not path.exists():raise RuntimeError('Word alignment missing. Run --project PATH --align-captions first, or set caption_mode to phrase.')
 data=read(path)
 if data['identity']!=identity(folder,clips) or len(data['lines'])!=len(clips):raise RuntimeError('Word alignment is stale; run --align-captions again')
 for i,(row,c) in enumerate(zip(data['lines'],clips),1):validate_words(row['words'],c['narration'],gs.duration(Path(folder)/'Voices'/f'line_{i:02d}.wav'))
 return data


def _from_saved_heygen_words(folder, clips):
 """Use the real word timestamps returned by the already-completed FREE HeyGen call.
 The audio split uses midpoints of quiet gaps; convert global speech times to
 line-relative times. Never regenerate audio, guess timings, or call network.
 """
 folder=Path(folder);path=folder/'heygen_word_timestamps.json'
 if not path.is_file():return None
 import gaming_shorts as gs
 data=read(path);timing=read(folder/'voice_timing.json')
 if data.get('voice_id')!=config()['voice_id'] or data.get('model')!='heygen-voice-1-turbo-free':
  raise RuntimeError('Saved HeyGen word timings do not use approved free Garret voice')
 script=[c['narration'].strip() for c in clips]
 if script!=data.get('script'):raise RuntimeError('Saved HeyGen word timing transcript differs from the imported plan')
 if abs(float(data['duration_seconds'])-float(timing['audio_duration_seconds']))>.10:
  raise RuntimeError('Saved HeyGen timing and downloaded audio durations differ')
 cuts=timing['segment_boundaries'];words=data['words']
 if len(cuts)!=len(clips)+1:raise RuntimeError('Incorrect narration segment boundary count')
 # Recover punctuation from approved text for meaningful stable caption groups.
 import re
 raw=[re.findall(r"[\w]+(?:['’][\w]+)*[.,!?;:]*",s) for s in script]
 if len(words)!=sum(map(len,raw)):raise RuntimeError('HeyGen word count differs from the approved narration')
 result=[];index=0;last_global=0.
 for i,(line,source_words) in enumerate(zip(clips,raw)):
  cut=float(cuts[i]);next_cut=float(cuts[i+1]);local=[]
  for token in source_words:
   w=words[index];index+=1;a=float(w['start']);b=float(w['end'])
   if tokens(w['word'])!=tokens(token):raise RuntimeError(f'HeyGen word mismatch in line {i+1}: {token!r}')
   if not last_global-.001<=a<b or a<cut-.015 or b>next_cut+.015:
    raise RuntimeError(f'HeyGen timestamps fall outside narration segment {i+1}')
   local.append({'word':token,'start':max(0.,a-cut),'end':b-cut})
   last_global=b
  measured=gs.duration(folder/'Voices'/f'line_{i+1:02d}.wav')
  validate_words(local,line['narration'],measured)
  result.append({'words':local})
 output={'identity':identity(folder,clips),'lines':result,
         'listening_review':'not_performed',
         'method':'actual source word timestamps returned by HeyGen; segment-relative midpoint cuts'}
 save(folder/'word_alignment.json',output)
 return output

def align(project):
 import gaming_shorts as gs
 p=Path(project);clips=gs.validate(p)['clips'];active=read(p/'active_voice.json');folder=p/active['folder']
 proof=read(folder/'provenance.json')
 from voices import request
 if proof['request_key']!=key(request(clips)):raise RuntimeError('Saved voice does not match current text; alignment will not synthesize replacements')
 for i in range(1,len(clips)+1):
  name=f'line_{i:02d}.wav'
  if digest(folder/'Voices'/name)!=proof['files'][name]:raise RuntimeError('Saved voice checksum mismatch')
 try:return load(folder,clips)
 except (OSError,KeyError,ValueError,RuntimeError):pass
 direct=_from_saved_heygen_words(folder,clips)
 if direct is not None:return direct
 python=Path(config().get('alignment_python',str(HERE/'.align-venv/bin/python')))
 if not python.is_file():raise RuntimeError('Alignment environment missing. Run bash setup_alignment.sh once (downloads local alignment dependencies/model).')
 job={'model':config()['alignment_model'],'lines':[{'audio':str(folder/'Voices'/f'line_{i:02d}.wav'),'text':c['narration']} for i,c in enumerate(clips,1)]}
 req=folder/'alignment_request.json';result=folder/'alignment_result.json';save(req,job)
 if result.exists():result.unlink()
 subprocess.run([str(python),str(HERE/'align_worker.py'),str(req),str(result)],check=True,timeout=config().get('alignment_timeout_seconds',1800))
 data=read(result);data['identity']=identity(folder,clips);data['listening_review']='not_performed';data['method']='stable-ts forced alignment of saved narration; not independent transcription verification'
 if len(data['lines'])!=len(clips):raise RuntimeError('Alignment returned wrong line count')
 for i,(row,c) in enumerate(zip(data['lines'],clips),1):validate_words(row['words'],c['narration'],gs.duration(folder/'Voices'/f'line_{i:02d}.wav'))
 save(folder/'word_alignment.json',data);return data

def groups(words):
 current=[]
 for w in words:
  if current and (len(current)>=5 or len(' '.join(x['word'] for x in current+[w]))>28 or w['start']-current[-1]['end']>.45):
   yield current;current=[]
  current.append(w)
  if re.search(r'[.!?;]$',w['word']):yield current;current=[]
 if current:yield current

def stamp(t,ass=False):
 ticks=round(t*(100 if ass else 1000));base=100 if ass else 1000
 seconds,sub=divmod(ticks,base);minutes,s=divmod(seconds,60);h,m=divmod(minutes,60)
 return f'{h}:{m:02d}:{s:02d}.{sub:02d}' if ass else f'{h:02d}:{m:02d}:{s:02d},{sub:03d}'
def escape(s):return s.replace('\\','').replace('{','').replace('}','').replace('\n',' ')

def write_ass(path, words, width, height, delay=0):
 """Stable karaoke phrases: entire group remains visible through silent gaps.
 Highlight only the current word in yellow; other words remain white.
 """
 size=round(width*.060)
 header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(2,round(width/270))},0,5,{round(width*.14)},{round(width*.14)},0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 events=[]
 for group in groups(words):
  # Include the between-word intervals: removing them causes caption flicker.
  a0=max(0.,float(group[0]['start'])-.04)
  end=float(group[-1]['end'])+.04
  boundaries=sorted({a0,end}|{float(w[k]) for w in group for k in ('start','end')})
  for a,b in zip(boundaries,boundaries[1:]):
   if b-a<.015:continue
   middle=(a+b)/2
   text=' '.join(('{\\1c&H00FFFF&}' if float(w['start'])<=middle<float(w['end']) else '{\\1c&HFFFFFF&}')+escape(w['word']) for w in group)
   text=f'{{\\pos({width//2},{round(height*.69)})}}'+text
   events.append(f'Dialogue: 0,{stamp(a+delay,True)},{stamp(b+delay,True)},Default,,0,0,0,,{text}')
 Path(path).write_text(header+'\n'.join(events)+'\n',encoding='utf-8')


def sidecars(out,lines,placements):
 words=[]
 for row,offset in zip(lines,placements):
  words.extend({'word':w['word'],'start':w['start']+offset,'end':w['end']+offset} for w in row['words'])
 save(Path(out)/'caption_timeline.json',{'words':words,'timing':'final video seconds','listening_review':'not_performed'})
 cues=[]
 for i,g in enumerate(groups(words),1):cues.append(f"{i}\n{stamp(g[0]['start'])} --> {stamp(g[-1]['end'])}\n"+' '.join(w['word'] for w in g))
 (Path(out)/'subtitles.srt').write_text('\n\n'.join(cues)+'\n',encoding='utf-8')
 warnings=[]
 for g in groups(words):
  if len(' '.join(w['word'] for w in g))/max(.01,g[-1]['end']-g[0]['start'])>20:warnings.append('Fast caption near '+str(round(g[0]['start'],2))+'s; review readability')
 return warnings
