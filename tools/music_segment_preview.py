"""Music-only preview from retained encoded gameplay and genuine saved narration."""
from pathlib import Path
import sys,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'Automation/gamingshorts_v2'))
from common import read,save,key,digest,config,run
import gaming_shorts as gs,music_library,music_mix,audio_pipeline
from audio_checks import indicators
root=Path(__file__).resolve().parents[1]
project=root/'Projects/V2/cairn_review_02_f7393e6c_main_quality_v1'
oldqc=read(project/'qc_report.json');old=Path(oldqc['review_sheet']).parent
video=old/'video.mp4';speech=old/'speech.wav';plan=read(project/'edit_plan.json')
evidence=root/'Releases/2026-11-13-music-segments';p=evidence/'preview_project';p.mkdir(exist_ok=True)
save(p/'edit_plan.json',plan)
track=music_library.select(p);assert track['path'],'Preview requires verified local music'
cfg=config();token=key({'video':digest(video),'speech':digest(speech),'music':track,'mixer':digest(root/'Automation/gamingshorts_v2/music_mix.py'),'config':cfg})[:12]
out=evidence/('preview_'+token);out.mkdir(exist_ok=True)
seconds=float(oldqc['expected_duration']);before={'video':digest(video),'narration':digest(speech)}
cut_times=[];offset=float(plan.get('opening_action',{}).get('duration',0))
for clip in plan['clips']:
    cut_times.append(offset);offset+=float(clip['duration'])
master,ref,bed,mixreport=music_mix.mix(speech,track,seconds,out,cfg,run,cuts=cut_times)
review=root/'ReadyForReview/music_segments_2026-11-13';review.mkdir(parents=True,exist_ok=True)
final=review/('cairn_segment_preview_'+token+'.mp4')
if final.exists():raise RuntimeError('Existing preview preserved: '+str(final))
run(['ffmpeg','-v','error','-nostdin','-i',video,'-i',master,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(seconds),'-movflags','+faststart',final])
words=read(old/'caption_timeline.json')['words'];windows=[]
for word in words:
    if not windows or word['start']-windows[-1][1]>.5:windows.append([word['start'],word['end']])
    else:windows[-1][1]=word['end']
windows=[w for w in windows if w[1]-w[0]>.15]
report=gs.qc(final,ref,bed,windows,seconds,out,cfg)
report['audio_mix']=mixreport;report['music']=track
report['final_loudness']=audio_pipeline.master_gain(final)
report['final_artifact_indicators']=indicators(gs.pcm(final,out/'final_artifact_check.wav'))
report['original_assets_unchanged']=before=={'video':digest(video),'narration':digest(speech)}
report['source']='Retained quality-repair encoded gameplay; no read or rewrite of full 59.5 GiB recording'
report['caption_timing']='Original burned-in word-aligned captions and video packets preserved; no timestamps shifted'
report['listening_review']='not_performed'
report['output']=str(final)
report['delivery_kind']='music_mix_demo'
report['new_story']=False
report['source_project']=str(project)
if report['final_artifact_indicators']['clipped_samples']:report['errors'].append('Final audio clipping')
if not report['original_assets_unchanged']:report['errors'].append('Retained source asset changed')
if report['final_loudness']['input_true_peak_db']>-.9:report['errors'].append('Encoded final true peak exceeds -0.9 dBTP')
report['status']='technical_pass' if not report['errors'] else 'failed'
save(out/'qc_report.json',report);save(review/'review_report.json',report)
if report['status']!='technical_pass':raise RuntimeError(str(report['errors']))
music_library.commit(p,track,final,token,mixreport['settings'],performance=report)
for name in ('subtitles.srt','caption_timeline.json'):
    if (old/name).exists():shutil.copyfile(old/name,final.with_suffix('.srt' if name.endswith('.srt') else '.captions.json'))
final.with_suffix('.music.txt').write_text(track['attribution']+'\n')
print('PASS:',final)
