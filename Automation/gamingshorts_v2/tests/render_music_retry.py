"""Small real render: safe no-music fallback, then music-only retry with no TTS/video encoding."""
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_regressions import tone
import common,gaming_shorts as gs,music_library,voices

with tempfile.TemporaryDirectory(prefix='music-retry-') as temp:
    root=Path(temp);p=root/'fixture';p.mkdir();gs.ROOT=root
    cfg=dict(common.DEFAULTS,width=180,height=320,fps=10,min_seconds=6,max_seconds=10,music_enabled=False,x264_preset='ultrafast')
    source=root/'source.mp4'
    common.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=10:d=6','-c:v','libx264','-threads','2',source])
    common.save(p/'manifest.json',{'source':str(source),'source_sha256':common.digest(source),'duration':6})
    clips=[{'start':i*2,'duration':2,'narration':'Synthetic test narration.','caption':'A TEST MOMENT'} for i in range(3)]
    common.save(p/'edit_plan.json',{'clips':clips})
    for i in range(1,4):tone(p/'Voices'/f'line_{i:02d}.wav',1.2)
    with patch.object(gs,'config',return_value=cfg),patch.object(music_library,'config',return_value=cfg):
        folder=voices.ensure(p,clips,adopt=True);hashes={v.name:common.digest(v) for v in (folder/'Voices').glob('*.wav')}
        first=gs.render(p,folder);assert gs.completed(p)
        assert common.read(p/'qc_report.json')['music']['path'] is None
        cfg['music_enabled']=True
        original=gs.run
        def guarded(command,**kwargs):
            if '-c:v' in command and command[command.index('-c:v')+1]=='libx264':raise AssertionError('Music retry encoded video')
            return original(command,**kwargs)
        with patch.object(gs,'run',side_effect=guarded),patch.object(voices.bridge,'generate_voice_with_codex',side_effect=AssertionError('Unexpected TTS')):
            assert voices.ensure(p,clips)==folder
            second=gs.render(p,folder)
        assert second!=first and gs.completed(p)
        assert hashes=={v.name:common.digest(v) for v in (folder/'Voices').glob('*.wav')}
        assert common.read(p/'qc_report.json')['audio_mix']['music_present']
        assert sum(t['usage']['uses'] for t in music_library.inventory())==1
        print('PASS: complete narration-only render, music-only retry, unchanged narration, no TTS, no video encoding, one successful Short usage.')
