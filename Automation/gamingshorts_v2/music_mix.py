"""Speech-led, bounded FFmpeg mixing. Never changes narration bytes or shot timing."""
import math
from pathlib import Path
import subprocess
import numpy as np
from common import digest,read,save
import audio_pipeline

DEFAULTS={'ducking':True,'threshold':.015,'ratio':8.,'attack_ms':15.,'release_ms':300.,'fade_in':.5,'fade_out':1.1,'target_lufs':-16.,'true_peak_db':-1.5,'gameplay_db':-26.,'beat_sync':True}

def settings(cfg):
    c=dict(DEFAULTS,**cfg.get('audio_mix',{}))
    if set(c)-set(DEFAULTS):raise ValueError('Unknown audio_mix setting')
    limits={'threshold':(.001,.5),'ratio':(1,20),'attack_ms':(1,500),'release_ms':(10,2000),'fade_in':(.01,3),'fade_out':(.02,5),'target_lufs':(-24,-12),'true_peak_db':(-6,-1),'gameplay_db':(-45,-12)}
    for name,(lo,hi) in limits.items():
        if not isinstance(c[name],(int,float)) or not math.isfinite(c[name]) or not lo<=c[name]<=hi:raise ValueError('Invalid audio_mix '+name)
    for field in ('ducking','beat_sync'):
        if not isinstance(c[field],bool):raise ValueError('Invalid audio_mix '+field)
    return c

def detect_beats(path,cache):
    """Bounded onset-energy estimate; no paid API and no claim of perfect beat tracking."""
    cache=Path(cache);sha=digest(path)
    if cache.exists():
        old=read(cache)
        if old.get('sha256')==sha:return old
    result=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-t','120','-ar','8000','-ac','1','-f','f32le','-'],capture_output=True,check=True)
    a=np.frombuffer(result.stdout,np.float32);n=len(a)//160
    if n<10:return {'sha256':sha,'beats':[],'bpm':0,'confidence':'insufficient'}
    rms=np.sqrt(np.mean(a[:n*160].reshape(n,160)**2,axis=1))
    onset=np.maximum(0,np.diff(rms,prepend=rms[0]));threshold=max(float(np.percentile(onset,85)),.001)
    peaks=[]
    for i in range(1,len(onset)-1):
        if onset[i]>threshold and onset[i]>=onset[i-1] and onset[i]>onset[i+1] and (not peaks or i-peaks[-1]>12):peaks.append(i)
    gaps=np.diff(peaks)*.02
    bpm=float(60/np.median(gaps)) if len(gaps)>2 else 0
    data={'sha256':sha,'beats':[round(i*.02,3) for i in peaks],'bpm':round(bpm,2),'confidence':'heuristic_onsets','seconds_analyzed':len(a)/8000}
    cache.parent.mkdir(parents=True,exist_ok=True);save(cache,data);return data

def beat_alignment(track,cuts,enabled=True):
    beats=track.get('beats',[])
    bpm=float(track.get('bpm',0) or 0)
    if not enabled or not beats or not cuts:return {'offset_seconds':0.,'method':'unaligned; gameplay timing preserved'}
    limit=min(2.,240/bpm) if bpm else 2.
    candidates=np.linspace(0,limit,81)
    offsets=[(sum(min(abs(float(b)-cut-off) for b in beats) for cut in cuts)/len(cuts),float(off)) for off in candidates]
    error,offset=min(offsets)
    return {'offset_seconds':round(offset,4),'mean_cut_to_beat_seconds':round(error,4),'method':'music phase only; no shot, speech or caption moved'}

def mix(speech,track,seconds,out,cfg,run,*,cuts=(),gameplay=None,log=None):
    out=Path(out);c=settings(cfg);samples=round(seconds*48000)
    exact=f'aresample=48000,apad=whole_len={samples},atrim=end_sample={samples},asetpts=N/SR/TB'
    bed=out/'music.wav';report={'policy':'speech-led-mix-v2','settings':c,'music_present':bool(track.get('path')),'gameplay_present':gameplay is not None}
    effective=dict(track)
    if track.get('path') and c['beat_sync'] and not track.get('beats'):
        estimated=detect_beats(track['path'],Path(cfg.get('root',out))/'Database/MusicAnalysis'/(digest(track['path'])+'.json'))
        effective['beats']=estimated['beats'];effective['bpm']=estimated['bpm']
        report['beat_detection']=estimated
    segment=track.get('segment')
    if segment:
        if segment['audio_sha256']!=track.get('sha256') or segment['seek_start']<segment['start'] or segment['seek_start']+seconds>segment['end']+.0001:
            raise ValueError('Selected music segment exceeds its exact-version evidence interval')
        alignment={'offset_seconds':segment['seek_start'],'method':'selected exact-version excerpt; music shifted, no gameplay or narration retimed','segment':segment}
    else:alignment=beat_alignment(effective,cuts,c['beat_sync'])
    report['beat_alignment']=alignment
    raw=out/'music_level.wav'
    if track.get('path'):
        offset=alignment['offset_seconds']
        run(['ffmpeg','-v','error','-nostdin','-y',* ([] if segment else ['-stream_loop','-1']),'-ss',str(offset),'-i',track['path'],'-t',str(seconds),'-af',f'loudnorm=I={cfg["music_lufs"]}:TP=-6:LRA=9,'+exact+f',afade=t=in:d={min(c["fade_in"],seconds/3)},afade=t=out:st={max(0,seconds-c["fade_out"])}:d={min(c["fade_out"],seconds)}','-ac','2','-c:a','pcm_f32le',raw],logfile=log)
    else:
        report['music_omission_reason']=track.get('reason','No approved music')
        run(['ffmpeg','-v','error','-nostdin','-y','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(seconds),'-c:a','pcm_f32le',raw],logfile=log)
    if track.get('path') and c['ducking']:
        graph=f'[0:a][1:a]sidechaincompress=threshold={c["threshold"]}:ratio={c["ratio"]}:attack={c["attack_ms"]}:release={c["release_ms"]}:makeup=1,'+exact+'[duck]'
        run(['ffmpeg','-v','error','-nostdin','-y','-i',raw,'-i',speech,'-filter_complex',graph,'-map','[duck]','-ac','2','-c:a','pcm_f32le',bed],logfile=log)
    else:
        run(['ffmpeg','-v','error','-nostdin','-y','-i',raw,'-c:a','pcm_f32le',bed],logfile=log)
    rawmix=out/'mix_unmastered.wav';inputs=['-i',speech,'-i',bed]
    graph='[0:a][1:a]amix=inputs=2:normalize=0'
    if gameplay is not None:
        inputs+=['-i',gameplay];graph='[0:a][1:a][2:a]amix=inputs=3:normalize=0'
    graph+=',alimiter=limit=0.95:level=0:latency=1,'+exact+f',afade=t=out:st={max(0,seconds-.025)}:d=0.025[a]'
    run(['ffmpeg','-v','error','-nostdin','-y',*inputs,'-filter_complex',graph,'-map','[a]','-c:a','pcm_f32le',rawmix],logfile=log)
    gain=audio_pipeline.master_gain(rawmix,c['target_lufs'],c['true_peak_db']);report['master_gain']=gain
    outputs=[]
    for src,name in ((rawmix,'mix_master.wav'),(speech,'speech_qc.wav'),(bed,'music_qc.wav')):
        dst=out/name
        run(['ffmpeg','-v','error','-nostdin','-y','-i',src,'-af',f'volume={gain["gain_db"]}dB,'+exact,'-ac','2','-c:a','pcm_f32le',dst],logfile=log);outputs.append(dst)
    measured=audio_pipeline.master_gain(outputs[0],c['target_lufs'],c['true_peak_db']);report['measured_lufs']=measured['input_lufs'];report['measured_true_peak_db']=measured['input_true_peak_db']
    if measured['input_true_peak_db']>c['true_peak_db']+.2:raise RuntimeError('Mixed master exceeds true peak limit')
    save(out/'audio_mix.json',report)
    return (*outputs,report)

def gameplay_stem(sources,out,seconds,cfg,run,probe,log=None):
    """Extract only actual audio streams; do not invent sound for silent sources."""
    c=settings(cfg);available={str(s['path']):any(x['codec_type']=='audio' for x in probe(s['path'])['streams']) for s in sources}
    if not any(available.values()) or cfg.get('preserve_gameplay_audio',True) is False:return None
    parts=[]
    for i,s in enumerate(sources):
        dst=Path(out)/f'gameplay_{i}.wav';d=float(s['duration'])
        if available[str(s['path'])]:
            cmd=['-threads','2','-ss',str(s['start']),'-i',s['path'],'-map','0:a:0','-af',f'volume={c["gameplay_db"]}dB,afade=t=in:d=0.01,afade=t=out:st={max(0,d-.02)}:d=0.02']
        else:cmd=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        run(['ffmpeg','-v','error','-nostdin','-y',*cmd,'-t',str(d),'-ac','2','-ar','48000','-c:a','pcm_f32le',dst],logfile=log);parts.append(dst)
    listing=Path(out)/'gameplay_concat.txt';listing.write_text(''.join("file '"+p.name+"'\n" for p in parts))
    dst=Path(out)/'gameplay.wav';run(['ffmpeg','-v','error','-nostdin','-y','-f','concat','-safe','0','-i',listing,'-t',str(seconds),'-c:a','pcm_f32le',dst],logfile=log)
    return dst
