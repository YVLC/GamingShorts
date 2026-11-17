"""Explicit V3 commands layered over the existing editorial DB and V2 worker."""

import argparse
import json
from pathlib import Path

from common import locked, read, configured_source, config
import gaming_shorts as gs
from game_store import GameStore, slug


def register(game, title, source):
    from job_store import JobStore
    from quality_checks import rate

    game = slug(game)
    source = Path(source).expanduser().resolve()
    folder = (gs.ROOT / "GameSources" / game).resolve()
    if (not source.is_relative_to(folder) and source != configured_source()) or source.is_symlink():
        raise ValueError(
            f"Place the original recording inside {folder}. Legacy Sources/ auto-discovers inputs; V3 deliberately does not."
        )
    proof = JobStore(gs.ROOT).admit_source(source)
    videos = [
        s
        for s in proof["probe"]["streams"]
        if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
    ]
    if len(videos) != 1 or not rate(videos[0].get("avg_frame_rate")):
        raise ValueError("A full-game recording must have one video stream with a known frame rate")
    video = videos[0]
    if int(video["width"]) < 1920 or int(video["height"]) < 1080:
        raise ValueError(
            "Use the high-quality original recording (at least 1920×1080), not an analysis proxy"
        )
    for stream in videos:
        import math

        if not math.isfinite(float(stream.get("start_time", 0))):
            raise ValueError("Invalid source timestamp origin")
    store = GameStore()
    result = store.register(game, title, proof)
    seed_bridge_exclusion(store, game)
    return result


def active_recording(store, *, start=False):
    """Configured selection is immediate; costly strict admission waits for --start."""
    selected = configured_source()
    if selected is None:
        return store.recording()
    try:
        current = store.recording()
    except ValueError:
        current = None
    if current and Path(current["source"]).resolve() == selected:
        return current
    if not start:
        return {"source": str(selected), "duration": float(gs.probe(selected)["format"]["duration"]),
                "status": "configured_pending_strict_registration"}
    game = config()["active_game"]
    register(game, game.title(), selected)
    return store.select(game)


def seed_bridge_exclusion(store, game):
    """Retain reference signatures across recordings; never modify historical media."""
    if game != "cairn":
        return
    label = "previously-overused-cairn-bridge"
    with store.connect() as db:
        if db.execute(
            "SELECT 1 FROM game_exclusions WHERE game=? AND label=?", (game, label)
        ).fetchone():
            return
    historical = gs.ROOT / "Projects/V2/cairn_review_02_f7393e6c_main_quality_v1"
    if not (historical / "manifest.json").exists() or not (historical / "edit_plan.json").exists():
        return  # Semantic bridge exclusion remains mandatory even without old exemplars.
    from game_index import visual_hashes
    import render_sources

    hashes = []
    manifest = read(historical / "manifest.json")
    for clip in read(historical / "edit_plan.json")["clips"]:
        if "bridge" not in (clip.get("evidence", "") + " " + clip.get("narration", "")).lower():
            continue
        try:
            resolved = render_sources.resolve(manifest, clip, gs.probe)
            hashes.extend(
                visual_hashes(
                    resolved["path"], resolved["start"], resolved["start"] + resolved["duration"]
                )
            )
        except (OSError, ValueError, RuntimeError):
            continue
    if hashes:
        with store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO game_exclusions VALUES (?,?,?,?)",
                (game, label, json.dumps(hashes), str(historical)),
            )


def parser():
    ap = argparse.ArgumentParser(prog="start.py --v3", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser(
        "register", help="Validate/hash an original; does not activate or analyze it"
    )
    p.add_argument("--game", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--source", type=Path, required=True)
    p = sub.add_parser("select", help="Explicit user-authorized active game selection")
    p.add_argument("--game", required=True)
    sub.add_parser("games", help="Registered games and explicit active selection")
    sub.add_parser(
        "estimate", help="Estimate full timeline proxy/storage requirements; no AI calls"
    )
    p = sub.add_parser("index", help="Index the full recording once; analysis is opt-in")
    p.add_argument("--start", action="store_true")
    p.add_argument("--retry", action="store_true")
    p.add_argument("--retry-ai", action="store_true")
    p.add_argument("--pilot-only", action="store_true", help="Local-first two-chunk bounded validation only")
    p = sub.add_parser("inventory", help="Unused scenes, coverage, exclusions and confidence")
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("history", help="Game, story, shots, queue and review/publication history")
    p.add_argument("--limit", type=int, default=50)
    p = sub.add_parser("reject-scene", help="Persistently exclude an indexed candidate")
    p.add_argument("--scene", required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("batch", help="Plan up to three distinct Shorts; never generates speech")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--start", action="store_true")
    p.add_argument("--retry", metavar="BATCH_ID")
    p.add_argument("--retry-ai", action="store_true")
    p = sub.add_parser(
        "run", help="Explicitly produce an existing planned batch using the V2 queue"
    )
    p.add_argument("--batch", required=True)
    p.add_argument("--start", action="store_true")
    p.add_argument("--retry", action="store_true")
    p = sub.add_parser("batch-status")
    p.add_argument("--batch", required=True)
    p = sub.add_parser(
        "close-batch", help="Explicitly abandon work; retain all assets and reservations"
    )
    p.add_argument("--batch", required=True)
    p.add_argument("--reason", required=True)
    return ap


def main(argv=None):
    ap = parser()
    a = ap.parse_args(argv)
    if a.command in ("index", "batch", "run") and not a.start:
        ap.error(
            "Add --start to explicitly authorize this analysis/production stage. Nothing was started."
        )
    if hasattr(a, "retry_ai") and a.retry_ai and not a.retry:
        ap.error("--retry-ai requires explicit --retry; it never authorizes a TTS retry")
    if hasattr(a, "limit") and not 1 <= a.limit <= 1000:
        ap.error("--limit must be 1–1000")
    if a.command == "index" and config().get("analysis_mode")=="local_first":
        from local_index import execute
        with locked(gs.ROOT / "Database/.workflow_v2.lock"):
            selected=active_recording(GameStore(), start=True)
            if a.retry_ai:
                from game_index import authorize_analysis_retry
                folder=gs.ROOT/"FootageIndex"/("sha256_"+selected["sha256"])/("LocalFirst_"+str(selected.get("index_key",""))[:16])
                authorize_analysis_retry(folder)
        execute(pilot_only=a.pilot_only)
        result=read(gs.ROOT/"Releases/2026-11-13-full-analysis/progress.json")
        print(json.dumps(result,indent=2))
        return result
    if a.command == "run":
        from game_plan import run_batch

        result = run_batch(a.batch, retry=a.retry)
    else:
        with locked(gs.ROOT / "Database/.workflow_v2.lock"):
            store = GameStore()
            if a.command == "register":
                result = register(a.game, a.title, a.source)
            elif a.command == "select":
                result = store.select(a.game)
            elif a.command == "games":
                with store.connect() as db:
                    result = {
                        "configured_source": str(configured_source()) if configured_source() else None,
                        "games": [dict(x) for x in db.execute("SELECT * FROM game_catalog")],
                        "active": [dict(x) for x in db.execute("SELECT * FROM game_settings")],
                    }
            elif a.command == "index":
                from game_index import index_recording

                active_recording(store, start=True)
                result = index_recording(retry=a.retry, retry_ai=a.retry_ai)
                result["scenes"] = result["scenes"][:50]
            elif a.command == "estimate":
                from game_index import estimate

                recording = active_recording(store)
                result = estimate(recording)
                result["source_status"] = recording["status"]
            elif a.command == "inventory":
                result = store.inventory()
                result["scenes"] = result["scenes"][: a.limit]
            elif a.command == "history":
                # Existing edits remain the canonical review/publication status.
                with editorial_connection() as db:
                    result = {
                        "batches": [
                            dict(x)
                            for x in db.execute(
                                "SELECT * FROM game_batches ORDER BY created DESC LIMIT ?",
                                (a.limit,),
                            )
                        ],
                        "stories": [
                            dict(x)
                            for x in db.execute(
                                """SELECT b.game,b.recording,i.project,i.job,e.hook,e.premise,e.structure,e.status,e.feedback
                          FROM game_batch_items i JOIN game_batches b ON b.id=i.batch
                          LEFT JOIN edits e ON e.project=i.project ORDER BY b.created DESC LIMIT ?""",
                                (a.limit,),
                            )
                        ],
                        "shots": [
                            dict(x)
                            for x in db.execute(
                                "SELECT * FROM game_shots ORDER BY rowid DESC LIMIT ?", (a.limit,)
                            )
                        ],
                    }
            elif a.command == "reject-scene":
                with store.connect() as db:
                    changed = db.execute(
                        "UPDATE game_scenes SET rejected=? WHERE id=?", (a.reason, a.scene)
                    )
                    if changed.rowcount != 1:
                        raise ValueError("Unknown scene")
                result = {"scene": a.scene, "rejected": a.reason}
            elif a.command == "batch":
                from game_plan import create_batch

                result = create_batch(a.count, resume=a.retry, retry_ai=a.retry_ai)
            elif a.command == "close-batch":
                result = store.close_batch(a.batch, a.reason)
            else:
                result = store.batch(a.batch)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def editorial_connection():
    # Initializes only additive existing editorial tables, preserving old rows.
    import editorial

    with editorial.connect():
        pass
    return GameStore().connect()
