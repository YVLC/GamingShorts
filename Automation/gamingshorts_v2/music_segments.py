"""Version-bound excerpt evidence, inferred musical structure, and stable selections.
Audio features never establish popularity. Only explicit, dated external evidence
can label a segment verified. No audio download or gameplay retiming exists here.
"""
import datetime as dt
import json,math,re,subprocess
from pathlib import Path
import numpy as np
from common import read,save,key,digest,now
import editorial

SCHEMA='''
CREATE TABLE IF NOT EXISTS music_versions_v1 (audio_sha256 TEXT PRIMARY KEY,track_id TEXT NOT NULL,version TEXT NOT NULL,duration REAL NOT NULL,analysis_key TEXT NOT NULL,analysis_json TEXT NOT NULL,created_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS music_segments_v1 (id TEXT PRIMARY KEY,track_id TEXT NOT NULL,audio_sha256 TEXT NOT NULL,version TEXT NOT NULL,start REAL NOT NULL,end REAL NOT NULL,climax REAL NOT NULL,status TEXT NOT NULL,confidence REAL NOT NULL,evidence_json TEXT NOT NULL,verified_date TEXT,mood TEXT NOT NULL,energy REAL NOT NULL,features_json TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS music_segment_pins_v1 (project TEXT NOT NULL,plan_key TEXT NOT NULL,track_hash TEXT NOT NULL,segment_id TEXT NOT NULL,snapshot_json TEXT NOT NULL,created_utc TEXT NOT NULL,PRIMARY KEY(project,plan_key,track_hash));
CREATE TABLE IF NOT EXISTS music_segment_results_v1 (project TEXT NOT NULL,render_key TEXT NOT NULL,segment_id TEXT NOT NULL,metrics_json TEXT NOT NULL,created_utc TEXT NOT NULL,PRIMARY KEY(project,render_key));
CREATE TABLE IF NOT EXISTS music_segment_feedback_v1 (id TEXT PRIMARY KEY,segment_id TEXT NOT NULL,metrics_json TEXT NOT NULL,evidence_url TEXT NOT NULL,observed_date TEXT NOT NULL);
'''

def initialize(db):
    for sql in SCHEMA.split(';'):
        if sql.strip():db.execute(sql)

def _rows(db,sql,args=()):
    cursor=db.execute(sql,args);names=[c[0] for c in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]

def analyze(track,cache):
    """Decode a bounded local music file once; identify structure, not trends."""
    if track.get('approval_status')!='approved' or track.get('usage_route')!='cleared':raise ValueError('Analyze only approved locally cleared music')
    sha=digest(track['path'])
    if sha!=track.get('approved_audio_sha256'):raise ValueError('Approved song bytes changed')
    version=track.get('version_id','sha256:'+sha)
    token=key({'audio':sha,'code':digest(__file__),'version':version,'policy':'musical-structure-v1'})
    cache=Path(cache)/('segments_'+token+'.json')
    if cache.exists():
        result=read(cache)
        if result['analysis_key']==token:
            store_analysis(result);return result
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(track['path'])],text=True))
    duration=float(probe['format']['duration'])
    if not math.isfinite(duration) or not 4<=duration<=600:raise ValueError('Music analysis supports 4-600 seconds; never feed a gameplay recording')
    decoded=subprocess.run(['ffmpeg','-v','error','-xerror','-i',track['path'],'-t',str(duration),'-ar','8000','-ac','1','-f','f32le','-'],capture_output=True,timeout=120,check=True)
    if decoded.stderr:raise ValueError(decoded.stderr.decode(errors='replace'))
    samples=np.frombuffer(decoded.stdout,np.float32);hop=256;size=512
    if len(samples)<size:raise ValueError('No decoded music samples')
    count=1+(len(samples)-size)//hop;energy=[];flux=[];previous=None
    window=np.hanning(size).astype(np.float32)
    # Small batches avoid materializing a full-song spectrogram in RAM.
    for i in range(count):
        frame=samples[i*hop:i*hop+size];spectrum=np.log1p(np.abs(np.fft.rfft(frame*window)))
        energy.append(float(np.sqrt(np.mean(frame**2))))
        flux.append(0. if previous is None else float(np.maximum(0,spectrum-previous).mean()))
        previous=spectrum
    energy=np.asarray(energy);flux=np.asarray(flux);step=hop/8000
    onset=np.maximum(0,flux-np.mean(flux));centered=onset-np.mean(onset)
    lags=range(round(.3/step),round(1./step)+1)
    lag=max(lags,key=lambda n:float(np.dot(centered[:-n],centered[n:]))) if len(centered)>100 else round(.5/step)
    period=lag*step;bpm=60/period
    threshold=float(np.percentile(onset,80));peaks=[]
    for i in range(1,len(onset)-1):
        if onset[i]>max(threshold,.0001) and onset[i]>=onset[i-1] and onset[i]>onset[i+1] and (not peaks or (i-peaks[-1])*step>.2):peaks.append(i)
    phase=(max(peaks[:max(1,round(8/step))],key=lambda i:onset[i])*step)%period if peaks else 0
    beats=[round(float(x),4) for x in np.arange(phase,duration,period)]
    # Phrase boundaries are hypotheses on an 8/16-beat grid and novelty edges.
    phrase_grid=[round(float(x),4) for x in np.arange(phase,duration,period*8)]
    radius=max(1,round(1.5/step));contrast=np.zeros(len(energy))
    for i in range(radius,len(energy)-radius):
        before=float(np.mean(energy[i-radius:i]));after=float(np.mean(energy[i:i+radius]))
        contrast[i]=20*math.log10((after+1e-6)/(before+1e-6))
    novelty=np.abs(contrast);transitions=[]
    for i in np.argsort(novelty)[::-1]:
        at=i*step
        if 5<at<duration-8 and all(abs(at-x)>8 for x in transitions):transitions.append(round(at,3))
        if len(transitions)==12:break
    drops=[]
    for i in np.argsort(contrast)[::-1]:
        at=i*step
        if contrast[i]>1.0 and 8<at<duration-10 and all(abs(at-x['at'])>18 for x in drops):
            drops.append({'at':round(at,3),'energy_rise_db':round(float(contrast[i]),3),'kind':'inferred_transition_not_popularity'})
        if len(drops)==6:break
    anchors=[d['at'] for d in drops]
    for at in np.arange(24,max(25,duration-12),40):
        if all(abs(float(at)-p)>15 for p in anchors):anchors.append(round(float(at),3))
    segments=[]
    for anchor in anchors[:10]:
        target=max(0,anchor-22)
        nearest=min(phrase_grid,key=lambda x:abs(x-target)) if phrase_grid else target
        start=max(0,min(nearest,max(0,duration-55)))
        end=min(duration,start+60)
        if end-start<8:continue
        segment={'id':key({'sha':sha,'version':version,'start':start,'end':end,'analysis':token})[:24],'track_id':track['id'],'audio_sha256':sha,'version':version,'start':round(start,4),'end':round(end,4),'climax':round(min(end,max(start,anchor)),4),'status':'inferred','confidence':0.,'evidence':[],'verified_date':None,'mood':track['mood'],'energy':float(track['energy']),'features':{'audio_confidence':.5,'popularity_confidence':0.,'method':'spectral onsets, energy-transition contrast and approximate phrase grid; NOT a verified trending excerpt','analysis_key':token}}
        if not any(abs(segment['start']-s['start'])<2 for s in segments):segments.append(segment)
    result={'analysis_key':token,'track_id':track['id'],'audio_sha256':sha,'version':version,'duration':duration,'bpm':round(bpm,3),'beats':beats,'phrase_boundaries':phrase_grid,'transitions':sorted(transitions),'drops':drops,'segments':segments,'popularity_claim':'none; audio analysis cannot verify a trend','method':'heuristic onset autocorrelation and phrase grid; boundaries are not human-confirmed'}
    cache.parent.mkdir(parents=True,exist_ok=True);save(cache,result)
    store_analysis(result);return result

def store_analysis(result):
    with editorial.connect() as db:
        initialize(db)
        db.execute('INSERT INTO music_versions_v1 VALUES (?,?,?,?,?,?,?) ON CONFLICT(audio_sha256) DO UPDATE SET version=excluded.version,analysis_key=excluded.analysis_key,analysis_json=excluded.analysis_json',(result['audio_sha256'],result['track_id'],result['version'],result['duration'],result['analysis_key'],json.dumps(result),now()))
        for s in result['segments']:_store(db,s)

def _store(db,s):
    db.execute('INSERT OR IGNORE INTO music_segments_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)',(s['id'],s['track_id'],s['audio_sha256'],s['version'],s['start'],s['end'],s['climax'],s['status'],s['confidence'],json.dumps(s['evidence']),s['verified_date'],s['mood'],s['energy'],json.dumps(s['features'])))

def import_verified(path):
    """Explicit evidence import; song-level chart ranks cannot verify excerpts."""
    entries=read(path)['segments'];valid=[]
    with editorial.connect() as db:
        initialize(db)
        for s in entries:
            version=db.execute('SELECT version,duration,track_id FROM music_versions_v1 WHERE audio_sha256=?',(s['audio_sha256'],)).fetchone()
            if not version or s['version']!=version[0] or s['track_id']!=version[2]:raise ValueError('Exact analyzed audio version required')
            a,b,c=[float(s[k]) for k in ('start','end','climax')]
            if not all(math.isfinite(n) for n in (a,b,c)) or not 0<=a<c<b<=version[1]:raise ValueError('Invalid verified interval')
            if not .6<=float(s['confidence'])<=1:raise ValueError('Verified confidence must be 0.6-1')
            date=dt.date.fromisoformat(s['verified_date'])
            if date>dt.datetime.now(dt.timezone.utc).date():raise ValueError('Future verification date')
            if not s.get('verified_by') or not s.get('evidence'):raise ValueError('Verifier and external evidence required')
            for e in s['evidence']:
                if e.get('scope')!='excerpt_popularity' or not re.match(r'^https?://',e.get('url','')) or not e.get('claim') or e.get('version')!=s['version']:raise ValueError('Excerpt-specific external evidence for this version required')
                if abs(float(e.get('song_start',-1))-a)>.1 or abs(float(e.get('song_end',-1))-b)>.1:raise ValueError('Evidence must support exact excerpt timestamps')
                observed=dt.date.fromisoformat(e['observed_date'])
                if observed>date:raise ValueError('Evidence date exceeds verification date')
            row=dict(s,status='verified',features={'verified_by':s['verified_by'],'popularity_confidence':s['confidence']})
            row['id']=key(row)[:24];valid.append(row)
        for s in valid:_store(db,s)
    return len(valid)

def list_segments(track_hash=None):
    with editorial.connect() as db:
        initialize(db)
        return _rows(db,'SELECT * FROM music_segments_v1 WHERE enabled=1'+(' AND audio_sha256=?' if track_hash else ''), (track_hash,) if track_hash else ())

def eligible_tracks(tracks,seconds):
    segments=list_segments();rank={}
    for track in tracks:
        if track.get('approval_status')!='approved' or track.get('usage_route')!='cleared':continue
        options=[s for s in segments if s['audio_sha256']==track['sha256'] and s['version']==track.get('version_id','sha256:'+track['sha256']) and s['end']-s['start']>=seconds]
        if options:rank[track['id']]=2 if any(s['status']=='verified' for s in options) else 1
    best=max(rank.values(),default=0)
    return [t for t in tracks if rank.get(t['id'])==best] if best else []

def gameplay_climax(plan):
    intro=float(plan.get('opening_action',{}).get('duration',0));total=intro+sum(float(c['duration']) for c in plan['clips'])
    explicit=plan.get('music',{}).get('climax_at')
    if explicit is not None:
        if not math.isfinite(float(explicit)) or not 0<=float(explicit)<=total:raise ValueError('Invalid gameplay climax')
        return float(explicit),'explicit editorial marker'
    points=[];offset=intro
    for i,clip in enumerate(plan['clips']):
        text=(str(clip.get('narration',''))+' '+str(clip.get('evidence',''))).lower()
        score=sum(len(re.findall(r'\b'+w+r'\b',text)) for w in ('danger','fall','slip','risk','rescue','recover','catch','save','jump','payoff','finally','surprise'))
        score+=float(clip.get('excitement',0))
        points.append((score,offset+float(clip['duration'])*.55));offset+=float(clip['duration'])
    at=max(points,key=lambda x:x[0])[1] if max(x[0] for x in points)>0 else total*.65
    return at,'narrative keyword/clip marker heuristic; not measured gameplay excitement'

def select_segment(project,track,plan):
    if not track.get('path') or track.get('approval_status')!='approved' or track.get('usage_route')!='cleared':return None
    project=str(Path(project));pk=key(plan);seconds=float(plan.get('opening_action',{}).get('duration',0))+sum(float(c['duration']) for c in plan['clips'])
    options=[s for s in list_segments(track['sha256']) if s['version']==track.get('version_id','sha256:'+track['sha256']) and s['end']-s['start']>=seconds]
    if not options:return None
    with editorial.connect() as db:
        initialize(db)
        pin=db.execute('SELECT snapshot_json FROM music_segment_pins_v1 WHERE project=? AND plan_key=? AND track_hash=?',(project,pk,track['sha256'])).fetchone()
        if pin:
            snapshot=json.loads(pin[0])
            if any(s['id']==snapshot['id'] and key(s)==snapshot['segment_proof_key'] for s in options):return snapshot
        climax,method=gameplay_climax(plan);choices=[]
        for s in options:
            offset=max(s['start'],min(s['end']-seconds,s['climax']-climax))
            error=abs((s['climax']-offset)-climax)
            feedback=[json.loads(r[0]) for r in db.execute('SELECT metrics_json FROM music_segment_feedback_v1 WHERE segment_id=?',(s['id'],))]
            scores=[]
            for f in feedback:
                if 'editor_rating' in f:scores.append(float(f['editor_rating']))
                # Audience observations are only a bounded tie-break, not a causal claim.
                if float(f.get('views',0))>=100 and 'average_view_percentage' in f:
                    scores.append(min(1.,float(f['average_view_percentage'])/100))
            rating=sum(scores)/len(scores) if scores else .5
            order=(s['status']!='verified',s['mood']!=track.get('profile',{}).get('mood',track['mood']),error,-float(s['confidence']),-rating,s['start'])
            choices.append((order,s,offset,error))
        _,s,offset,error=min(choices,key=lambda x:x[0])
        snapshot={'id':s['id'],'version':s['version'],'audio_sha256':s['audio_sha256'],'start':s['start'],'end':s['end'],'seek_start':round(offset,6),'seek_end':round(offset+seconds,6),'source_climax':s['climax'],'gameplay_climax':round(climax,6),'climax_alignment_error_seconds':round(error,6),'gameplay_climax_method':method,'status':s['status'],'popularity_confidence':s['confidence'] if s['status']=='verified' else 0.,'evidence':json.loads(s['evidence_json']),'verified_date':s['verified_date'],'features':json.loads(s['features_json']),'segment_proof_key':key(s),'policy':'segment-selector-v1'}
        db.execute('INSERT INTO music_segment_pins_v1 VALUES (?,?,?,?,?,?) ON CONFLICT(project,plan_key,track_hash) DO UPDATE SET segment_id=excluded.segment_id,snapshot_json=excluded.snapshot_json,created_utc=excluded.created_utc',(project,pk,track['sha256'],s['id'],json.dumps(snapshot),now()))
    return snapshot

def record_result(project,render_key,selected,metrics):
    segment=selected.get('segment')
    if not segment:return
    with editorial.connect() as db:
        initialize(db);db.execute('INSERT OR IGNORE INTO music_segment_results_v1 VALUES (?,?,?,?,?)',(str(project),render_key,segment['id'],json.dumps(metrics),now()))

def import_feedback(path):
    rows=read(path)['results']
    with editorial.connect() as db:
        initialize(db)
        for row in rows:
            if not db.execute('SELECT 1 FROM music_segments_v1 WHERE id=?',(row['segment_id'],)).fetchone():raise ValueError('Unknown segment')
            if not re.match(r'^https?://',row.get('evidence_url','')):raise ValueError('Performance evidence URL required')
            dt.date.fromisoformat(row['observed_date'])
            for name,value in row['metrics'].items():
                if name not in ('editor_rating','views','likes','average_view_percentage') or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError('Invalid performance metric')
                if name=='editor_rating' and value>1:raise ValueError('Editor rating must be 0-1')
            db.execute('INSERT OR IGNORE INTO music_segment_feedback_v1 VALUES (?,?,?,?,?)',(key(row),row['segment_id'],json.dumps(row['metrics']),row['evidence_url'],row['observed_date']))
    return len(rows)
