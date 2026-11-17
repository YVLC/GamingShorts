"""Local music management; no downloading, publishing or paid services."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import HERE,config,read,save,digest,now
import music_library as music
from music_mix import detect_beats
import music_segments


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('list');sub.add_parser('trends')
    for name in ('import-library','import-trends','import-segments','segment-feedback'):
        p=sub.add_parser(name);p.add_argument('json_file',type=Path)
    p=sub.add_parser('approve');p.add_argument('track_id');p.add_argument('--basis',required=True);p.add_argument('--youtube-ugc',action='store_true',required=True)
    p=sub.add_parser('beats');p.add_argument('track_id')
    p=sub.add_parser('segments');p.add_argument('--track-id')
    p=sub.add_parser('analyze-segments');p.add_argument('track_id')
    a=ap.parse_args();path=Path(config().get('music_catalog',str(HERE/'music_catalog.json')))
    if a.cmd=='list':result={'approved_local_tracks':music.inventory(),'catalog':str(path),'all_entries':read(path).get('tracks',[]) if path.exists() else [],'capacity':'unbounded; 20+ tracks supported'}
    elif a.cmd=='trends':result=music.trends()
    elif a.cmd=='import-trends':result={'imported':music.import_trends(a.json_file),'note':'metadata only; no audio rights granted by trend imports'}
    elif a.cmd=='import-segments':result={'imported_verified_evidence_records':music_segments.import_verified(a.json_file),'note':'Evidence must have been externally reviewed; schema validation does not establish popularity'}
    elif a.cmd=='segment-feedback':result={'imported':music_segments.import_feedback(a.json_file)}
    elif a.cmd=='segments':
        sha=next(t['sha256'] for t in music.inventory() if t['id']==a.track_id) if a.track_id else None
        result=music_segments.list_segments(sha)
    elif a.cmd=='analyze-segments':
        track=next(t for t in music.inventory() if t['id']==a.track_id)
        result=music_segments.analyze(track,Path(config()['root'])/'Database/MusicAnalysis')
    else:
        data=read(path) if path.exists() else {'tracks':[]}
        if a.cmd=='import-library':
            tracks=read(a.json_file)['tracks'];ids={t['id'] for t in data['tracks']}
            if len({t['id'] for t in tracks})!=len(tracks) or any(t['id'] in ids for t in tracks):raise ValueError('Duplicate ID; existing tracks preserved')
            for track in tracks:
                track=dict(track,approval_status='pending')
                # Imported relative paths resolve against the input document, not our runtime.
                for field in ('path','license_evidence'):
                    if track.get(field):track[field]=str((a.json_file.resolve().parent/track[field]).resolve())
                data['tracks'].append(track)
            save(path,data);result={'imported_pending':len(tracks)}
        else:
            track=next(t for t in data['tracks'] if t['id']==a.track_id)
            if a.cmd=='beats':
                audio=path.parent/track['path'];result=detect_beats(audio,HERE/'music/analysis'/(digest(audio)+'.json'))
                # Heuristic estimates are evidence, not silently approved metadata edits.
            else:
                if track.get('usage_route')!='cleared':raise ValueError('Platform-only/unknown tracks cannot be approved for rendering')
                audio=path.parent/track['path'];evidence=path.parent/track['license_evidence']
                track.update(approval_status='approved',approval_basis=a.basis,approval_utc=now(),permitted_use='youtube_ugc',approved_audio_sha256=digest(audio),approved_evidence_sha256=digest(evidence))
                old=read(path) if path.exists() else None
                save(path,data)
                try:music.catalog()
                except BaseException:
                    if old is not None:save(path,old)
                    raise
                result={'approved':a.track_id,'note':'Approval records your evidence review; it is not an automated legal judgement'}
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
