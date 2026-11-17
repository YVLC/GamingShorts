"""Local, explicitly cleared music; durable reservations are not usage counts."""
from pathlib import Path
import datetime as dt
import json
import math
import subprocess
import re
from common import HERE, config, read, save, digest, key, now
import editorial

MOODS = {'suspense':('danger risk slip narrow tense suspense fall rescue hold',.55), 'epic':('summit victory triumph epic impressive overcome final',.85), 'funny':('funny unexpected absurd fail laugh stumble comic',.6), 'relaxed':('relax calm peaceful explore scenic rest discover',.25), 'action':('fast jump chase sprint action frantic combat dodge',.95)}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS music_tracks_v2 (id TEXT PRIMARY KEY,sha256 TEXT NOT NULL,metadata_json TEXT NOT NULL,synced_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS music_assignments_v2 (project TEXT NOT NULL,plan_key TEXT NOT NULL,selection_key TEXT NOT NULL,track_hash TEXT,selection_json TEXT NOT NULL,status TEXT NOT NULL,created_utc TEXT NOT NULL,committed_utc TEXT,output TEXT,output_sha256 TEXT,render_key TEXT,audio_config_json TEXT,PRIMARY KEY(project,plan_key));
CREATE TABLE IF NOT EXISTS music_selection_events_v2 (project TEXT NOT NULL,plan_key TEXT NOT NULL,selection_key TEXT NOT NULL,selection_json TEXT NOT NULL,created_utc TEXT NOT NULL,PRIMARY KEY(project,plan_key,selection_key));
CREATE TABLE IF NOT EXISTS music_render_events_v2 (project TEXT NOT NULL,plan_key TEXT NOT NULL,render_key TEXT NOT NULL,selection_json TEXT NOT NULL,audio_config_json TEXT NOT NULL,output TEXT NOT NULL,output_sha256 TEXT NOT NULL,created_utc TEXT NOT NULL,PRIMARY KEY(project,plan_key,render_key));
CREATE VIEW IF NOT EXISTS music_successful_use_v2 AS SELECT e.project,json_extract(e.selection_json,'$.sha256') AS track_hash,e.created_utc AS committed_utc FROM music_render_events_v2 e WHERE e.rowid=(SELECT r.rowid FROM music_render_events_v2 r WHERE r.project=e.project ORDER BY r.created_utc DESC,r.rowid DESC LIMIT 1);
CREATE TABLE IF NOT EXISTS music_trends_v2 (id TEXT PRIMARY KEY,metadata_json TEXT NOT NULL,imported_utc TEXT NOT NULL);
'''

def initialize(db):
    for statement in SCHEMA.split(';'):
        if statement.strip(): db.execute(statement)

def profile(plan):
    text=' '.join([str(plan.get('editorial',{}))]+[str(c.get('narration',''))+' '+str(c.get('evidence','')) for c in plan['clips']]).lower()
    scores={m:sum(len(re.findall(r'\b'+re.escape(w)+r'\b',text)) for w in words.split()) for m,(words,_) in MOODS.items()}
    override=plan.get('music',{}).get('mood')
    mood=override if override in MOODS else max(scores,key=scores.get) if max(scores.values()) else 'suspense'
    pace=len(plan['clips'])/max(1,sum(float(c['duration']) for c in plan['clips']))
    return {'mood':mood,'energy':round(min(1.,MOODS[mood][1]+max(0,pace-.2)),3),'cuts_per_second':round(pace,3),'method':'explicit mood or keyword/shot-pace heuristic','keyword_scores':scores}

def catalog(*,strict=True):
    p=Path(config().get('music_catalog',str(HERE/'music_catalog.json')))
    if not p.exists():return []
    data=read(p);tracks=[];seen=set();ids=set();errors=[]
    for t in data.get('tracks',[]):
        if not t.get('enabled',True):continue
        try:
            for field in ('id','title','artist','source','genre','mood','license','license_evidence','source_url','path','approval_status','usage_route'):
                if not isinstance(t.get(field),str) or not t[field].strip() or t[field].startswith('REPLACE'):raise ValueError('Music track missing '+field)
            if t['id'] in ids:raise ValueError('Music IDs must be unique')
            ids.add(t['id'])
            if t['approval_status']!='approved' or t['usage_route']!='cleared':continue
            if t.get('permitted_use')!='youtube_ugc' or not isinstance(t.get('attribution'),str):raise ValueError('Missing YouTube scope or attribution')
            if t.get('attribution_required') and not t['attribution'].strip():raise ValueError('Required attribution missing')
            if t['mood'] not in MOODS or not 0<=float(t['energy'])<=1:raise ValueError('Invalid mood/energy')
            bpm=float(t.get('bpm',0))
            if not math.isfinite(bpm) or not 0<=bpm<=300:raise ValueError('Invalid BPM')
            audio=Path(t['path']);audio=audio if audio.is_absolute() else p.parent/audio
            evidence=Path(t['license_evidence']);evidence=evidence if evidence.is_absolute() else p.parent/evidence
            if not audio.is_file() or not evidence.is_file():raise ValueError('Missing local audio/license evidence')
            sha=digest(audio);proof=digest(evidence)
            if sha!=t.get('approved_audio_sha256') or proof!=t.get('approved_evidence_sha256'):raise ValueError('Approved audio or license evidence changed')
            expires=t.get('approval_expires')
            if expires and dt.date.fromisoformat(expires)<dt.datetime.now(dt.timezone.utc).date():raise ValueError('Music approval expired')
            beats=t.get('beats',[])
            if not isinstance(beats,list) or any(not isinstance(b,(int,float)) or not math.isfinite(b) or b<0 for b in beats) or beats!=sorted(set(beats)):raise ValueError('Invalid beat timestamps')
            if sha in seen:continue
            seen.add(sha);tracks.append(dict(t,path=str(audio.resolve()),license_evidence=str(evidence.resolve()),sha256=sha,license_evidence_sha256=proof))
        except (ValueError,KeyError,TypeError,OSError) as error:errors.append(f"{t.get('id','unknown')}: {error}")
    if errors and strict:raise ValueError('; '.join(errors))
    return tracks

def silence(reason,wanted=None):
    return {'id':None,'path':None,'sha256':None,'attribution':'','usage_route':'none','license':'No music mixed','reason':reason,'profile':wanted,'policy':'music-v2'}

def select(project):
    p=Path(project);plan=read(p/'edit_plan.json');pk=key(plan);wanted=profile(plan)
    try:tracks=catalog()
    except (OSError,ValueError,TypeError) as error:tracks=[];reason='No music: catalog validation failed: '+str(error)
    else:reason='No approved, local music cleared for YouTube UGC'
    if plan.get('music',{}).get('instrumental_only'):tracks=[t for t in tracks if t.get('instrumental') is True]
    if config().get('music_enabled',True) is False:tracks=[];reason='Music disabled in configuration'
    recent_trends=[]
    for trend in trends():
        age=(dt.datetime.now(dt.timezone.utc).date()-dt.date.fromisoformat(trend['discovery_date'])).days
        if 0<=age<=30 and trend['permitted_usage_route']=='cleared' and trend['platform'].lower()=='youtube':
            recent_trends.append(trend)
    trend_ids={t.get('library_track_id') for t in recent_trends}
    strategy=config().get('music_strategy','library')
    if strategy=='story_music' and plan.get('editorial',{}).get('policy') not in ('gaming-stories-v1','gaming-stories-v2'):strategy='library'
    if strategy not in ('library','trending_then_new_original','segments_then_new_original','story_music'):raise ValueError('Invalid music_strategy')
    if strategy=='story_music' and plan.get('music',{}).get('allow_vocals',False) is False:
        tracks=[t for t in tracks if t.get('instrumental') is True]
    requested=plan.get('music',{}).get('track_ids',[])
    if requested:
        if not isinstance(requested,list) or not all(isinstance(x,str) for x in requested):raise ValueError('Invalid requested library track IDs')
        tracks=[t for t in tracks if t['id'] in requested]
        if set(t['id'] for t in tracks)!=set(requested):raise ValueError('Requested music is missing or not cleared; no generated substitution')
        # Explicitly requested local songs retain their existing rights checks,
        # rotation and approved segment selection, without procedural fallback.
        strategy='requested_library_segments'
    if strategy=='segments_then_new_original' and config().get('music_enabled',True):
        from music_segments import eligible_tracks
        length=float(plan.get('opening_action',{}).get('duration',0))+sum(float(c['duration']) for c in plan['clips'])
        candidates=eligible_tracks(tracks,length)
        if candidates:tracks=candidates
        else:
            from music_composer import compose
            try:tracks=[compose(p,plan,wanted,editorial.gs.ROOT)]
            except (OSError,ValueError,subprocess.SubprocessError) as error:tracks=[];reason='Fresh original unavailable: '+str(error)
    if strategy=='trending_then_new_original' and config().get('music_enabled',True):
        trending=[t for t in tracks if t['id'] in trend_ids]
        if trending:tracks=trending
        else:
            from music_composer import compose
            try:tracks=[compose(p,plan,wanted,editorial.gs.ROOT)]
            except (OSError,ValueError,subprocess.SubprocessError) as error:tracks=[];reason='Fresh original composition unavailable: '+str(error)
    if strategy in ('segments_then_new_original','requested_library_segments','story_music'):
        from music_segments import select_segment
        tracks=[dict(t,segment=select_segment(p,dict(t,profile=wanted),plan)) for t in tracks]
    token=key({'policy':'music-v3' ,'tracks':tracks,'profile':wanted,'cleared_trends':recent_trends,'strategy':strategy})
    with editorial.connect() as db:
        initialize(db);db.execute('BEGIN IMMEDIATE')
        for track in tracks:db.execute('INSERT INTO music_tracks_v2 VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET sha256=excluded.sha256,metadata_json=excluded.metadata_json,synced_utc=excluded.synced_utc',(track['id'],track['sha256'],json.dumps(track),now()))
        prior=db.execute('SELECT selection_key,selection_json FROM music_assignments_v2 WHERE project=? AND plan_key=?',(str(p),pk)).fetchone()
        if prior and prior[0]==token:chosen=json.loads(prior[1])
        else:
            last=db.execute('SELECT track_hash FROM music_assignments_v2 WHERE track_hash IS NOT NULL AND project!=? ORDER BY created_utc DESC,rowid DESC LIMIT 1',(str(p),)).fetchone()
            counts=dict(db.execute("SELECT track_hash,count(*) FROM music_successful_use_v2 WHERE track_hash IS NOT NULL GROUP BY track_hash"))
            recency=dict(db.execute("SELECT track_hash,max(committed_utc) FROM music_successful_use_v2 GROUP BY track_hash"))
            eligible=[t for t in tracks if not last or t['sha256']!=last[0]]
            if not config().get('music_rotation',True):eligible=tracks
            # A suitable mood outranks rotation for story-led edits. Rotation
            # breaks ties; it must not replace emotional music with comic music.
            if strategy=='story_music':eligible=tracks
            if eligible:
                rank=lambda t:(counts.get(t['sha256'],0),t['mood']!=wanted['mood'],abs(float(t['energy'])-wanted['energy']),t['id'] not in trend_ids,recency.get(t['sha256']) or '',t['id'])
                if strategy=='story_music':
                    rank=lambda t:(t['mood']!=wanted['mood'],t.get('instrumental') is not True,t['id'] not in trend_ids,abs(float(t['energy'])-wanted['energy']),bool(last and t['sha256']==last[0]),counts.get(t['sha256'],0),recency.get(t['sha256']) or '',t['id'])
                chosen=min(eligible,key=rank)
                chosen=dict(chosen,profile=wanted,policy='music-v2',reason='Least-used, mood/energy fit, recent cleared trend tie-break, oldest successful use; consecutive reuse excluded')
                if strategy=='story_music':chosen.update(policy='story-music-v1',reason='Story mood, instrumental preference, recent cleared YouTube trend evidence, energy fit and rotation; vocal music only when plan permits it',trend_verified=chosen['id'] in trend_ids)
            else:chosen=silence('Consecutive-track prevention: no different approved track' if tracks else reason,wanted)
            db.execute("INSERT INTO music_assignments_v2(project,plan_key,selection_key,track_hash,selection_json,status,created_utc) VALUES (?,?,?,?,?,'reserved',?) ON CONFLICT(project,plan_key) DO UPDATE SET selection_key=excluded.selection_key,track_hash=excluded.track_hash,selection_json=excluded.selection_json,status='reserved',created_utc=excluded.created_utc,committed_utc=NULL,output=NULL,output_sha256=NULL,render_key=NULL,audio_config_json=NULL",(str(p),pk,token,chosen['sha256'],json.dumps(chosen),now()))
        db.execute('INSERT OR IGNORE INTO music_selection_events_v2 VALUES (?,?,?,?,?)',(str(p),pk,token,json.dumps(chosen),now()))
    save(p/'music_selection.json',chosen)
    if strategy=='story_music' and not chosen.get('path'):raise ValueError('No cleared music fits this story and its vocal policy; no speech requested')
    return chosen

def commit(project,selected,output,render_key,audio_config,performance=None):
    p=Path(project);pk=key(read(p/'edit_plan.json'));output=Path(output);sha=digest(output)
    if performance is not None and (performance.get('status')!='technical_pass' or Path(performance.get('output','')).resolve()!=output.resolve()):
        raise ValueError('Music usage requires technical QC for this output')
    with editorial.connect() as db:
        initialize(db);db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT selection_json FROM music_assignments_v2 WHERE project=? AND plan_key=?',(str(p),pk)).fetchone()
        if not row or json.loads(row[0])!=selected:raise RuntimeError('Music reservation changed during render')
        db.execute('INSERT OR IGNORE INTO music_render_events_v2 VALUES (?,?,?,?,?,?,?,?)',(str(p),pk,render_key,json.dumps(selected),json.dumps(audio_config),str(output),sha,now()))
        db.execute("UPDATE music_assignments_v2 SET status='committed',committed_utc=COALESCE(committed_utc,?),output=?,output_sha256=?,render_key=?,audio_config_json=? WHERE project=? AND plan_key=?",(now(),str(output),sha,render_key,json.dumps(audio_config),str(p),pk))

    if selected.get('segment'):
        from music_segments import record_result
        report=performance or {}
        if report and (report.get('status')!='technical_pass' or Path(report.get('output','')).resolve()!=output.resolve()):
            raise ValueError('Segment performance must describe this technically validated output')
        record_result(p,render_key,selected,{'kind':'technical_qc_not_audience_performance','status':report.get('status','technical_pass'),'audio_windows':report.get('audio_windows',[]),'audio_mix':report.get('audio_mix',{}),'output_sha256':sha})

def inventory():
    tracks=catalog(strict=False)
    with editorial.connect() as db:
        initialize(db)
        known={t['sha256'] for t in tracks}
        for row in db.execute('SELECT metadata_json FROM music_tracks_v2'):
            track=json.loads(row[0])
            if track.get('source')!='generated_per_short' or track['sha256'] in known:continue
            try:
                if digest(track['path'])!=track['approved_audio_sha256'] or digest(track['license_evidence'])!=track['approved_evidence_sha256']:continue
            except OSError:continue
            tracks.append(track);known.add(track['sha256'])
        counts={r[0]:{'uses':r[1],'last_used':r[2]} for r in db.execute("SELECT track_hash,count(*),max(committed_utc) FROM music_successful_use_v2 GROUP BY track_hash")}
    return [dict(t,usage=counts.get(t['sha256'],{'uses':0,'last_used':None})) for t in tracks]

def import_trends(path):
    rows=read(path)['trends'];ids=set()
    for row in rows:
        for f in ('id','title','artist','platform','discovery_date','popularity_evidence','permitted_usage_route','source_url'):
            if not isinstance(row.get(f),str) or not row[f].strip():raise ValueError('Trend missing '+f)
        if row['id'] in ids:raise ValueError('Duplicate trend ID')
        ids.add(row['id']);dt.date.fromisoformat(row['discovery_date'])
        if row['permitted_usage_route'] not in ('platform_only','cleared','unknown'):raise ValueError('Invalid trend route')
        if row['permitted_usage_route']=='cleared' and not row.get('library_track_id'):raise ValueError('Cleared trend needs independently approved local track')
    with editorial.connect() as db:
        initialize(db)
        for row in rows:db.execute('INSERT INTO music_trends_v2 VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET metadata_json=excluded.metadata_json,imported_utc=excluded.imported_utc',(row['id'],json.dumps(row),now()))
    return len(rows)

def trends():
    with editorial.connect() as db:
        initialize(db);return [json.loads(r[0]) for r in db.execute('SELECT metadata_json FROM music_trends_v2')]
