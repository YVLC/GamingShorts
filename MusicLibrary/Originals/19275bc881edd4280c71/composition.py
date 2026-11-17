"""Fresh deterministic instrumental per Short; no external samples or music calls."""
from pathlib import Path
import json,hashlib,subprocess,tempfile,wave
import numpy as np
from common import digest,key,read,save,locked

def compose(project,plan,wanted,root):
    project=Path(project);root=Path(root)
    identity=key({'project':str(project.resolve()),'plan':plan,'composer':digest(__file__)})[:20]
    folder=root/'MusicLibrary/Originals'/identity
    with locked(root/'Database/.music_composer.lock'):
        proof=folder/'provenance.json';audio=folder/'instrumental.mp3'
        if proof.exists():
            facts=read(proof)
            if not audio.exists() or facts['audio_sha256']!=digest(audio) or facts['composition_sha256']!=digest(folder/'composition.py'):
                raise ValueError('Generated music changed; original artifacts preserved')
        else:
            if audio.exists():raise ValueError('Incomplete generated track preserved for inspection')
            folder.mkdir(parents=True,exist_ok=True)
            rate=48000;seconds=64
            rng=np.random.default_rng(int(identity[:16],16));mood=wanted['mood']
            bpm=int(rng.integers(80,101)) if mood in ('suspense','relaxed') else int(rng.integers(108,133))
            beat=60/bpm;tonic=int(rng.choice([45,47,48,50,52,54]))
            scale=[0,2,3,5,7,8,10] if mood in ('suspense','action') else [0,2,4,5,7,9,11]
            progression=[int(n) for n in rng.choice([0,3,4,5],4,replace=False)]
            melody=rng.integers(0,7,32).tolist();signal=np.zeros((seconds*rate,2),np.float64)
            def note(midi,at,length,gain,pan=0,pad=False):
                start=round(at*rate);size=min(round(length*rate),len(signal)-start)
                if size<=0:return
                t=np.arange(size)/rate;f=440*2**((midi-69)/12)
                env=np.minimum(1,t/(.22 if pad else .025))*np.minimum(1,(length-t)/min(.7,length*.45))
                if not pad:env*=np.exp(-t/(.8 if mood=='action' else 1.3))
                v=gain*env*(np.sin(2*np.pi*f*t)+.12*np.sin(4*np.pi*f*t))
                signal[start:start+size,0]+=v*np.sqrt((1-pan)/2);signal[start:start+size,1]+=v*np.sqrt((1+pan)/2)
            for bar,at in enumerate(np.arange(0,seconds,4*beat)):
                degree=progression[(bar//2)%4];base=tonic+scale[degree]
                for j,interval in enumerate([0,3 if mood in ('suspense','action') else 4,7]):note(base+12+interval,at,beat*4+.15,.032,(j-1)*.3,True)
                for n in range(4):note(base-12,at+n*beat,beat*.9,.09 if n%2==0 else .05)
                for step in range(8):
                    degree=melody[(bar*3+step)%32]
                    note(tonic+24+scale[degree],at+step*beat/2,beat*1.8,.047,(-1 if step%2 else 1)*.3)
            signal*=.62/max(.62,float(np.max(np.abs(signal))))
            fade=np.minimum(1,np.arange(len(signal))/(rate*1.4))*np.minimum(1,np.arange(len(signal))[::-1]/(rate*2.3))
            signal*=fade[:,None]
            with tempfile.TemporaryDirectory() as temp:
                wav=Path(temp)/'composition.wav'
                with wave.open(str(wav),'wb') as f:
                    f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes((signal*32767).astype('<i2').tobytes())
                result=subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(wav),'-c:a','libmp3lame','-b:a','192k',str(audio)],capture_output=True,text=True,timeout=120,check=True)
                if result.stderr:raise ValueError(result.stderr)
            code=Path(__file__).read_bytes();(folder/'composition.py').write_bytes(code)
            facts={'id':'original_'+identity,'title':mood.title()+' Study '+identity[:6],'artist':'GamingShorts procedural composition','source':'generated_per_short','project':str(project),'origin':'New composition synthesized for this Short at user request; no external samples, loops, recordings or melody inputs.','permitted_use':'Created for the user-owned GamingShorts project; no third-party audio licensed or included.','audio_sha256':digest(audio),'composition_sha256':digest(folder/'composition.py'),'mood':mood,'bpm':bpm,'seconds':seconds,'melody_degrees':melody,'progression_degrees':progression,'external_samples':[],'listening_review':'not_performed'}
            save(proof,facts)
        return {'id':facts['id'],'title':facts['title'],'artist':facts['artist'],'source':'generated_per_short','path':str(audio.resolve()),'sha256':facts['audio_sha256'],'genre':'original instrumental electronic','mood':facts['mood'],'energy':wanted['energy'],'bpm':facts['bpm'],'beats':[round(i*60/facts['bpm'],6) for i in range(int(facts['seconds']*facts['bpm']/60))],'license':'Original procedural composition for this project; no third-party source audio','license_evidence':str(proof.resolve()),'license_evidence_sha256':digest(proof),'approved_audio_sha256':facts['audio_sha256'],'approved_evidence_sha256':digest(proof),'source_url':'workspace:MusicLibrary/Originals/'+identity+'/composition.py','approval_status':'approved','approval_basis':'User requested fresh generated fallback; deterministic source provenance retained','usage_route':'cleared','permitted_use':'youtube_ugc','attribution':'Original GamingShorts instrumental: '+facts['title'],'attribution_required':False,'instrumental':True}
