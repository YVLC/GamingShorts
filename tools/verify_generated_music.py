from pathlib import Path
import sys,json,subprocess
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import digest,save,HERE
from music_library import catalog
from audio_checks import indicators
results=[]
for track in catalog():
    evidence=json.loads((HERE/track['license_evidence']).read_text())
    assert evidence['audio_sha256']==digest(track['path'])
    code=Path(__file__).resolve().parents[1]/evidence['composition_source']
    assert evidence['composition_sha256']==digest(code)
    assert not evidence['external_samples'] and not evidence['external_compositions']
    result=subprocess.run(['ffmpeg','-v','error','-xerror','-i',track['path'],'-ar','16000','-ac','1','-f','s16le','-'],capture_output=True,check=True)
    assert not result.stderr
    signal=np.frombuffer(result.stdout,dtype='<i2')
    qc=indicators(signal)
    assert qc['clipped_samples']==0 and not qc['possible_impulse_seconds']
    results.append({'id':track['id'],'duration':len(signal)/16000,'qa':qc,'provenance_checks':'pass'})
save(Path(__file__).resolve().parents[1]/'Releases/2026-11-13-timestamp-validation/music-qc.json',results)
print('PASS:',len(results),'generated tracks: provenance, full decode, no clipping or isolated impulse indicators.')

