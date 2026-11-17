"""Additive full-game catalog in the existing editorial SQLite database.

The production queue remains automation.sqlite3; these tables are editorial
inventory and reservations, not a second worker queue.
"""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import re
import sqlite3

from common import key, now, read
import gaming_shorts as gs


SCHEMA = """
CREATE TABLE IF NOT EXISTS game_catalog (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, recording TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS game_settings (id INTEGER PRIMARY KEY CHECK(id=1), active_game TEXT);
CREATE TABLE IF NOT EXISTS game_recordings (
 id TEXT PRIMARY KEY, game TEXT NOT NULL, source TEXT NOT NULL, sha256 TEXT NOT NULL,
 fingerprint TEXT NOT NULL, probe_json TEXT NOT NULL, duration REAL NOT NULL,
 index_key TEXT, status TEXT NOT NULL, error TEXT, created TEXT NOT NULL,
 UNIQUE(game,sha256));
CREATE TABLE IF NOT EXISTS game_chunks (
 recording TEXT NOT NULL, index_key TEXT NOT NULL, ordinal INTEGER NOT NULL,
 start REAL NOT NULL, end REAL NOT NULL, status TEXT NOT NULL,
 artifact_json TEXT, error TEXT, PRIMARY KEY(recording,index_key,ordinal));
CREATE TABLE IF NOT EXISTS game_scenes (
 id TEXT PRIMARY KEY, recording TEXT NOT NULL, index_key TEXT NOT NULL,
 chunk INTEGER NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
 description TEXT NOT NULL, category TEXT NOT NULL, confidence REAL NOT NULL,
 evidence TEXT NOT NULL, tags_json TEXT NOT NULL,
 hashes_json TEXT NOT NULL, score REAL NOT NULL, rejected TEXT);
CREATE INDEX IF NOT EXISTS game_scenes_inventory ON game_scenes(recording,index_key,score);
CREATE TABLE IF NOT EXISTS game_batches (
 id TEXT PRIMARY KEY, game TEXT NOT NULL, recording TEXT NOT NULL, index_key TEXT NOT NULL,
 count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS game_batch_items (
 batch TEXT NOT NULL, ordinal INTEGER NOT NULL, project TEXT NOT NULL UNIQUE,
 candidate_json TEXT NOT NULL, job TEXT, PRIMARY KEY(batch,ordinal));
CREATE TABLE IF NOT EXISTS game_shots (
 project TEXT NOT NULL, scene TEXT NOT NULL, recording TEXT NOT NULL,
 start REAL NOT NULL, end REAL NOT NULL, hashes_json TEXT NOT NULL,
 PRIMARY KEY(project,start,end));
CREATE TABLE IF NOT EXISTS game_exclusions (
 game TEXT NOT NULL, label TEXT NOT NULL, hashes_json TEXT NOT NULL,
 provenance TEXT NOT NULL, PRIMARY KEY(game,label));
"""


def slug(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", value):
        raise ValueError("Game IDs use lowercase letters, digits, underscores or hyphens")
    return value


def interval(a, b, duration):
    a, b = float(a), float(b)
    if not all(math.isfinite(v) for v in (a, b, duration)) or not 0 <= a < b <= duration:
        raise ValueError("Timestamp range is outside the authoritative recording")
    return a, b


def overlaps(a, b, x, y):
    return min(b, y) - max(a, x) > 0.001


def visually_similar(left, right, threshold=6):
    """Conservative perceptual guard, not semantic understanding or identity proof."""
    return any((int(a, 16) ^ int(b, 16)).bit_count() <= threshold for a in left for b in right)


class GameStore:
    def __init__(self):
        self.path = gs.ROOT / "Database/editorial_v2.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(SCHEMA)
            if "spoiler" in {r[1] for r in db.execute("PRAGMA table_info(game_scenes)")}:
                backup=gs.ROOT/"Releases/2026-11-14-gaming-stories/legacy-database.sqlite3"
                backup.parent.mkdir(parents=True,exist_ok=True)
                if not backup.exists():
                    with sqlite3.connect(backup) as target:db.backup(target)
                db.execute("ALTER TABLE game_scenes DROP COLUMN spoiler")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def recording(self, identity=None):
        with self.connect() as db:
            if identity:
                row = db.execute("SELECT * FROM game_recordings WHERE id=?", (identity,)).fetchone()
            else:
                row = db.execute("""SELECT r.* FROM game_settings s
                    JOIN game_catalog g ON g.id=s.active_game
                    JOIN game_recordings r ON r.id=g.recording WHERE s.id=1""").fetchone()
        if row is None:
            raise ValueError("No active game/source. Register and explicitly select one first.")
        return dict(row)

    def register(self, game, title, proof):
        game = slug(game)
        doc = proof["probe"]
        duration = float(doc["format"]["duration"])
        identity = key({"game": game, "sha256": proof["sha256"]})[:24]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM game_catalog WHERE id=?", (game,)).fetchone()
            if prior and prior["recording"] != identity:
                raise ValueError(
                    "This game already has an authoritative recording; preserved. Use a new game ID for a replacement edition."
                )
            existing = db.execute(
                "SELECT * FROM game_recordings WHERE id=?", (identity,)
            ).fetchone()
            if existing and (
                existing["source"] != proof["source"]
                or existing["fingerprint"] != proof["fingerprint"]
            ):
                raise ValueError(
                    "Recording already registered at different path/metadata; no silent source rebinding"
                )
            db.execute(
                "INSERT OR IGNORE INTO game_recordings VALUES (?,?,?,?,?,?,?,NULL,'registered',NULL,?)",
                (
                    identity,
                    game,
                    proof["source"],
                    proof["sha256"],
                    proof["fingerprint"],
                    json.dumps(doc),
                    duration,
                    now(),
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO game_catalog VALUES (?,?,?,?)",
                (game, title, identity, now()),
            )
        return self.recording(identity)

    def select(self, game):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM game_catalog WHERE id=?", (game,)).fetchone():
                raise ValueError("Unknown game; register its original recording first")
            running = db.execute(
                "SELECT 1 FROM game_batches WHERE status IN ('planning','running')"
            ).fetchone()
            if running:
                raise ValueError("A batch needs recovery/completion before switching games")
            db.execute(
                "INSERT INTO game_settings VALUES (1,?) ON CONFLICT(id) DO UPDATE SET active_game=excluded.active_game",
                (game,),
            )
        return self.recording()

    def scenes(self, recording=None):
        r = self.recording(recording)
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM game_scenes WHERE recording=? AND index_key=? ORDER BY score DESC,start",
                (r["id"], r["index_key"]),
            ).fetchall()
        return [dict(row) for row in rows]

    def eligible(self, scene, *, project=None, extra=()):
        contextual=False
        if project and (Path(project)/'scene_context.json').is_file():
            context=read(Path(project)/'scene_context.json')
            if scene['id'] in context.get('supporting_scene_ids',[]) and scene['confidence']>=.9 and not scene['rejected']:
                with self.connect() as db:
                    anchor=db.execute('SELECT * FROM game_scenes WHERE id=?',(context.get('anchor_scene_id'),)).fetchone()
                if anchor and anchor['recording']==scene['recording'] and anchor['confidence']>=.75 and anchor['score']>=.5 and not anchor['rejected'] and anchor['category'] not in ('map','menu','static','unknown'):
                    r=self.recording(scene['recording'])
                    contextual=(context.get('source_sha256')==r['sha256'] and bool(context.get('purpose','').strip()) and
                        abs(scene['start']-anchor['start'])<=90)
        if (
            scene["confidence"] < 0.75
            or (scene["score"] < 0.5 and not contextual)
            or scene["rejected"]
        ):
            return False
        if scene["category"] in ("map", "menu", "static", "unknown") and not contextual:
            return False
        r = self.recording(scene["recording"])
        from story_policy import reuse_allowed
        reuse=reuse_allowed(r['sha256'])
        if (
            r["game"] == "cairn"
            and "bridge"
            in (" ".join(json.loads(scene["tags_json"])) + " " + scene["description"]).lower()
        ):
            return False
        hashes = json.loads(scene["hashes_json"])
        if not hashes:
            return False
        with self.connect() as db:
            excluded = db.execute(
                "SELECT hashes_json FROM game_exclusions WHERE game=?", (r["game"],)
            ).fetchall()
            used = db.execute(
                "SELECT * FROM game_shots WHERE project!=?", (str(project or ""),)
            ).fetchall()
            # V2 history on the identical source remains authoritative too.
            tables = {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            legacy = (
                db.execute(
                    "SELECT start,end FROM footage_reservations WHERE source_hash=? AND project!=?",
                    (r["sha256"], str(project or "")),
                ).fetchall()
                if "footage_reservations" in tables
                else []
            )
        if any(visually_similar(hashes, json.loads(x["hashes_json"])) for x in excluded):
            return False
        for other in ([] if reuse else list(used)) + list(extra):
            if (
                other["recording"] == scene["recording"]
                and overlaps(scene["start"], scene["end"], other["start"], other["end"])
            ) or visually_similar(hashes, json.loads(other["hashes_json"])):
                return False
        return reuse or not any(overlaps(scene["start"], scene["end"], x["start"], x["end"]) for x in legacy)

    def inventory(self):
        r = self.recording()
        scenes = self.scenes(r["id"])
        with self.connect() as db:
            chunks = [
                dict(x)
                for x in db.execute(
                    "SELECT ordinal,start,end,status,error FROM game_chunks WHERE recording=? AND index_key=? ORDER BY ordinal",
                    (r["id"], r["index_key"]),
                )
            ]
        return {
            "recording": r,
            "chunks": chunks,
            "scenes": [dict(x, eligible=self.eligible(x)) for x in scenes],
            "available": sum(self.eligible(x) for x in scenes),
        }

    def reserve(self, project, plan, scenes):
        """Caller holds the workflow lock; commit every shot atomically."""
        p = Path(project)
        if (p/'scene_context.json').is_file():
            context=read(p/'scene_context.json')
            total=sum(float(c['duration']) for c in plan['clips'])
            central=sum(float(c['duration']) for c in plan['clips'] if c.get('scene_id')==context.get('anchor_scene_id'))
            if central<total*.4:raise ValueError('Supporting context must not replace the central demonstrated event')
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Recheck eligibility while holding SQLite's writer reservation.
            staged = []
            for clip in plan["clips"]:
                scene = next((s for s in scenes if s["id"] == clip.get("scene_id")), None)
                if scene is None or not self.eligible(scene, project=p):
                    raise ValueError("Scene is no longer unused or eligible")
                a, b = interval(
                    clip["start"],
                    float(clip["start"]) + float(clip["duration"]),
                    self.recording(scene["recording"])["duration"],
                )
                if a < scene["start"] or b > scene["end"]:
                    raise ValueError("Shot extends beyond inspected evidence")
                if any(overlaps(a, b, x[3], x[4]) for x in staged):
                    raise ValueError("Repeated footage within batch story")
                staged.append((str(p), scene["id"], scene["recording"], a, b, scene["hashes_json"]))
            for row in staged:
                db.execute("INSERT OR IGNORE INTO game_shots VALUES (?,?,?,?,?,?)", row)

    def batch(self, identity):
        with self.connect() as db:
            row = db.execute("SELECT * FROM game_batches WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise ValueError("Unknown batch")
            items = [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM game_batch_items WHERE batch=? ORDER BY ordinal", (identity,)
                )
            ]
        return dict(row, items=items)

    def close_batch(self, identity, reason):
        """Explicit abandonment keeps all plans, reservations, narration and outputs."""
        if not reason.strip():
            raise ValueError("A reason is required to close a batch")
        batch = self.batch(identity)
        if batch["status"] == "running":
            raise ValueError("Recover the interrupted running batch before closing it")
        from common import locked
        from job_store import JobStore

        with locked(gs.ROOT / "Database/.automation.lock"):
            queue = JobStore(gs.ROOT)
            for item in batch["items"]:
                if not item["job"]:
                    continue
                job = queue.get(item["job"])
                if job["status"] == "running":
                    raise ValueError("Cannot close a batch with a running worker")
                if job["status"] == "queued":
                    queue.finish(
                        job["id"], "needs_attention", error="Batch closed by user: " + reason
                    )
            with self.connect() as db:
                db.execute(
                    "UPDATE game_batches SET status='closed',error=? WHERE id=?", (reason, identity)
                )
        return self.batch(identity)
