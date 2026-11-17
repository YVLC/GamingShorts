"""Check the actual edited samples against the preserved free speech master."""
import sys,subprocess,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,digest
import gaming_shorts as gs
import numpy as np
release=gs.ROOT/'Releases/2026-11-15-story-reuse';p=Path(read(release/'rainbow_logic_plan.json')['project'])
folder=p/read(p/'active_voice.json')['folder'];proof=read(folder/'provenance.json');mapping=proof['derivation']
source=Path(mapping['source_folder'])/'Audio/heygen_full.wav';target=folder/'Audio/heygen_full.wav'
if digest(source)!=mapping['source_master_sha256']:raise ValueError('Original speech master changed')
def pcm(path):
    meta=gs.probe(path);stream=next(s for s in meta['streams'] if s['codec_type']=='audio')
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-'],capture_output=True,check=True).stdout
    return np.frombuffer(raw,dtype='<f4').reshape(-1,int(stream['channels'])),int(stream['sample_rate'])
old,rate=pcm(source);new,new_rate=pcm(target)
if rate!=new_rate:raise ValueError('Unexpected speech rate change')
lo,hi=mapping['removed_source_samples'];expected=np.concatenate([old[:lo],old[hi:]])
if expected.shape!=new.shape:raise ValueError('Incorrect audio edit length')
margin=round(rate*.006);mask=np.ones(len(new),dtype=bool);mask[max(0,lo-margin):min(len(mask),lo+margin)]=False
error=float(np.max(np.abs(expected[mask]-new[mask])))
if error>1e-6:raise ValueError('Retained speech samples changed beyond documented boundary fades')
result={'status':'passed','origin':proof['origin'],'source_sha256':digest(source),'derived_sha256':digest(target),
        'removed_words':mapping['removed_words'],'removed_samples':hi-lo,'sample_rate':rate,
        'retained_samples_max_error_outside_boundary_fades':error,'new_speech_generated':False}
save(release/'audio-trim-verification.json',result);print(json.dumps(result))
