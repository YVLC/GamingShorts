"""Keep the three current previews separate from preserved framing prototypes."""
import sys,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,digest,locked
import gaming_shorts as gs
release=gs.ROOT/'Releases/2026-11-15-story-reuse';root=(gs.ROOT/'ReadyForReview/cairn_stories_2026-11-15').resolve();archive=root/'previous_versions'
with locked(gs.ROOT/'Database/.workflow_v2.lock'):
    archive.mkdir(exist_ok=True)
    for receipt in (release/'framing_prototypes').glob('*_delivery.json'):
        old=read(receipt);event=receipt.name.removesuffix('_delivery.json');current=read(release/(event+'_delivery.json'))
        source=Path(old['output']).resolve()
        if source==Path(current['output']).resolve():raise ValueError('Current delivery cannot be archived')
        if not source.is_relative_to(root):raise ValueError('Prototype is outside this review folder')
        target=(archive/source.name).resolve()
        if not target.is_relative_to(root):raise ValueError('Archive target escaped review folder')
        for ext in ('.mp4','.srt','.captions.json','.music.txt','.upload.json'):
            a=source.with_suffix(ext);b=target.with_suffix(ext)
            if a==b:continue
            if a.exists():
                if b.exists():raise ValueError('Refusing to overwrite an archived version')
                shutil.move(str(a),str(b))
        if digest(target)!=old['sha256']:raise ValueError('Archived prototype bytes changed')
        old.update(output=str(target),previous_review_path=str(source));save(receipt,old)
    print('Current previews separated from preserved earlier framing versions.')
