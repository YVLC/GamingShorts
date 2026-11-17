"""Source-wide still-image cache for multi-Short planning. Never transcodes or copies the original recording."""

from __future__ import annotations
import math
from pathlib import Path
from common import config, digest, key, read, save
import gaming_shorts as gs

INDEX_VERSION = 1


def _source(project):
    m = read(Path(project) / "manifest.json")
    src = Path(m["source"]).resolve()
    if not src.is_file():
        raise RuntimeError(f"Source recording missing: {src}")
    st = src.stat()
    if m.get("source_size_bytes") is not None and st.st_size != int(m["source_size_bytes"]):
        raise RuntimeError("Source changed size; cannot trust existing footage index")
    if m.get("source_modified_ns") is not None and st.st_mtime_ns != int(m["source_modified_ns"]):
        raise RuntimeError(
            "Source modified since project creation; cannot trust cached visual index"
        )
    if not m.get("source_sha256"):
        raise ValueError("Source SHA256 missing from manifest")
    return src, m


def _root(meta):
    return gs.ROOT / "FootageIndex" / ("sha256_" + meta["source_sha256"])


def surveys(project):
    """Generate eight timestamped survey sheets ONCE per source, reuse for all variants."""
    src, m = _source(project)
    import editorial  # lazy import: editorial uses shared_index

    sec = float(m["duration"])
    cfg = config()
    font_sha = digest(cfg["font"])
    if not math.isfinite(sec) or sec <= 0:
        raise ValueError("Invalid recording duration")
    folder = _root(m) / "PlanningSurveys_v1"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = folder / "cache.json"
    items = [folder / f"survey_{i:02d}.jpg" for i in range(8)]
    expected = {
        "index_version": INDEX_VERSION,
        "source_sha256": m["source_sha256"],
        "duration_seconds": sec,
        "font_sha256": font_sha,
        "sheet_count": 8,
    }
    old = read(stamp) if stamp.exists() else {}
    valid = all(old.get(k) == v for k, v in expected.items())
    if valid:
        valid = all(
            p.is_file()
            and p.stat().st_size >= 800
            and digest(p) == old.get("image_sha256", {}).get(p.name)
            for p in items
        )
    if valid:
        print("Reusing 8 cached whole-recording survey sheets (no rescan).", flush=True)
        return items
    for i, p in enumerate(items):
        print(f"Indexing source once: overview {i + 1}/8", flush=True)
        editorial.sheet(src, sec * i / 8, sec / 8, p, "survey")
    expected["image_sha256"] = {p.name: digest(p) for p in items}
    save(stamp, expected)
    return items


def dense(project, start, seconds):
    """Cache selected close-up sheet by source + exact timestamp, across project variants."""
    src, m = _source(project)
    cfg = config()
    start = float(start)
    seconds = float(seconds)
    if (
        not math.isfinite(start)
        or not math.isfinite(seconds)
        or start < 0
        or seconds <= 0
        or start + seconds > float(m["duration"]) + 0.02
    ):
        raise ValueError("Invalid dense-preview range")
    token = key(
        {
            "version": INDEX_VERSION,
            "source_sha256": m["source_sha256"],
            "start": round(start, 6),
            "seconds": round(seconds, 6),
            "font_sha256": digest(cfg["font"]),
        }
    )
    folder = _root(m) / "PlanningDense_v1"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{token}.jpg"
    proof = folder / f"{token}.json"
    if dest.exists() and proof.exists() and dest.stat().st_size >= 800:
        try:
            if read(proof).get("sha256") == digest(dest):
                print(
                    f"Reusing previously inspected window: {start:.1f}–{start + seconds:.1f}s",
                    flush=True,
                )
                return dest
        except (OSError, ValueError, KeyError):
            pass
    import editorial

    editorial.sheet(src, start, seconds, dest, "dense")
    save(proof, {"sha256": digest(dest), "start": start, "duration": seconds})
    return dest


def dense_proxy(project, scene, start, seconds):
    """Reuse a checked analysis proxy for discovery; exact final evidence uses dense()."""
    from game_store import GameStore
    from common import run
    import shutil
    _,meta=_source(project);store=GameStore();r=store.recording(scene['recording'])
    with store.connect() as db:
        row=db.execute('SELECT start,end,artifact_json FROM game_chunks WHERE recording=? AND index_key=? AND ordinal=?',(r['id'],r['index_key'],scene['chunk'])).fetchone()
    if not row or start<max(row['start'],scene['start']) or start+seconds>min(row['end'],scene['end']) or seconds<=0:
        raise ValueError('Proxy preview outside indexed scene/chunk')
    root=_root(meta)/('LocalFirst_'+r['index_key'][:16])/f"chunk_{scene['chunk']:05d}"
    proof=read(root/'artifacts.json');proxy=root/'analysis.mp4'
    if proof['start']!=row['start'] or proof['end']!=row['end'] or digest(proxy)!=proof['files']['analysis.mp4']:
        raise ValueError('Proxy changed or timestamp origin is untrusted')
    cfg=config();identity=key({'version':1,'source':r['sha256'],'proxy':proof['files']['analysis.mp4'],
        'start':start,'seconds':seconds,'font':digest(cfg['font'])})
    folder=_root(meta)/'ProxyPlanning_v1';folder.mkdir(parents=True,exist_ok=True)
    dest=folder/(identity+'.jpg');receipt=folder/(identity+'.json')
    if dest.exists() and receipt.exists() and read(receipt)['sha256']==digest(dest):return dest
    shutil.copyfile(cfg['font'],folder/'font.ttf')
    vf=(f"scale=320:180,settb=AVTB,setpts=PTS-STARTPTS+{start:.6f}/TB,"
        "drawtext=fontfile=font.ttf:text='%{pts\\:hms}':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.7:x=4:y=4,"
        f"fps=16/{seconds:.6f},tile=4x4")
    run(['ffmpeg','-v','error','-nostdin','-y','-ss',start-row['start'],'-t',seconds,'-i',proxy,
         '-an','-vf',vf,'-frames:v','1','-update','1',dest],cwd=folder,logfile=folder/'frames.log')
    if not dest.is_file() or dest.stat().st_size<800:raise ValueError('Proxy evidence sheet missing')
    save(receipt,{'sha256':digest(dest),'absolute_start':start,'duration':seconds,'proxy_origin':row['start'],
                  'source_sha256':r['sha256'],'limitation':'2 fps proxy discovery; exact selected footage is inspected from original before approval'})
    return dest
