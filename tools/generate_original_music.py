"""Original instrumental cues: deterministic synthesis, no samples or model calls.
Every note is specified here; envelopes return to zero to avoid boundary clicks.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'Automation/gamingshorts_v2/music/generated_2026_11_13'
RATE=48000
SECONDS=64

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def tone(midi, seconds, gain, pad=False):
    t=np.arange(round(seconds*RATE))/RATE
    freq=440*2**((midi-69)/12)
    attack=.25 if pad else .025
    release=min(1.2, seconds*.45)
    envelope=np.minimum(1,t/attack)*np.minimum(1,(seconds-t)/release)
    if not pad: envelope*=np.exp(-t/1.1)
    signal=np.sin(2*np.pi*freq*t)+.16*np.sin(2*np.pi*2*freq*t)+.05*np.sin(2*np.pi*3*freq*t)
    return gain*envelope*signal

def generate():
    DEST.mkdir(parents=True,exist_ok=True)
    tracks=[]; qc=[]
    specs=[('thin_air',47,84,[0,3,7,10],[0,5,3,7]),('small_victory',50,96,[0,4,7,11],[0,7,5,9]),('steady_hands',45,90,[0,3,7,10],[0,3,5,7]),('one_more_hold',52,102,[0,3,7,10],[0,5,7,3]),('hidden_path',48,78,[0,2,7,9],[0,5,7,2])]
    for idx,(name,root,bpm,chord,progression) in enumerate(specs):
        out=DEST/(name+'.mp3')
        if out.exists(): raise RuntimeError('Preserving existing generated track: '+str(out))
        audio=np.zeros((SECONDS*RATE,2),dtype=np.float64)
        beat=60/bpm
        def add(note,at,duration,gain,pan=0,pad=False):
            start=round(at*RATE)
            values=tone(note,duration,gain,pad)[:max(0,len(audio)-start)]
            if start>=len(audio):return
            audio[start:start+len(values),0]+=values*np.sqrt((1-pan)/2)
            audio[start:start+len(values),1]+=values*np.sqrt((1+pan)/2)
        for bar,at in enumerate(np.arange(0,SECONDS,beat*4)):
            shift=progression[(bar//2)%len(progression)]
            for j,note in enumerate(chord[:3]):add(root+shift+note+12,at,beat*4+.35,.035,(j-1)*.3,True)
            add(root+shift-12,at,beat*2,.12)
            add(root+shift-12,at+beat*2,beat*1.6,.09)
            for step in range(8):
                note=chord[(step+bar+idx)%len(chord)]
                add(root+shift+note+24,at+step*beat/2,beat*1.8,.055,(-1 if step%2 else 1)*.25)
        peak=float(np.max(np.abs(audio)))
        audio*=.65/max(peak,.65)
        fade=np.minimum(1,np.arange(len(audio))/(RATE*1.5))*np.minimum(1,np.arange(len(audio))[::-1]/(RATE*2.5))
        audio*=fade[:,None]
        assert not np.any(np.abs(audio)>=1)
        with tempfile.TemporaryDirectory() as temp:
            wav=Path(temp)/'synthesis.wav'
            with wave.open(str(wav),'wb') as f:
                f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE);f.writeframes((audio*32767).astype('<i2').tobytes())
            subprocess.run(['ffmpeg','-v','error','-i',str(wav),'-c:a','libmp3lame','-b:a','192k',str(out)],check=True)
        evidence=DEST/(name+'.provenance.json')
        facts={'id':name,'origin':'Original deterministic procedural instrumental, generated for GamingShorts at user request.','composition_source':str(Path(__file__).relative_to(ROOT)),'composition_sha256':sha(Path(__file__)),'audio_sha256':sha(out),'external_samples':[],'external_compositions':[],'generative_service':None,'third_party_audio_license_required':False,'use':'Created for use in the user-owned GamingShorts videos; no third-party recordings, loops, melodies or music services supplied.','bpm':bpm,'sample_rate':RATE,'seconds':SECONDS,'seed':idx,'listening_review':'not_performed'}
        evidence.write_text(json.dumps(facts,indent=2)+'\n')
        tracks.append({'id':'generated_'+name,'path':str(out.relative_to(ROOT/'Automation/gamingshorts_v2')),'license':'Original procedural synthesis created for this project; no third-party source audio','license_evidence':str(evidence.relative_to(ROOT/'Automation/gamingshorts_v2')),'source_url':'workspace:tools/generate_original_music.py','attribution':'Original procedural GamingShorts instrumental: '+name.replace('_',' '),'enabled':True})
        qc.append({'id':name,'peak_dbfs':float(20*np.log10(np.max(np.abs(audio)))),'max_adjacent_step':float(np.max(np.abs(np.diff(audio,axis=0)))),'start':audio[0].tolist(),'end':audio[-1].tolist(),'clipped_samples':0})
    (DEST/'synthesis-qc.json').write_text(json.dumps(qc,indent=2)+'\n')
    catalog=ROOT/'Automation/gamingshorts_v2/music_catalog.json'
    if catalog.exists(): raise RuntimeError('Existing catalog preserved; merge explicitly')
    catalog.write_text(json.dumps({'tracks':tracks},indent=2)+'\n')
    print('Generated',len(tracks),'distinct original instrumental cues with provenance.')

if __name__=='__main__':generate()
