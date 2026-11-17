"""Durable queue, content identity and reusable successful integrity receipts."""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import time

from common import digest, key, now, save
from source_validation import (
    SourceValidationError,
    decode_source,
    fingerprint,
    inspect_source,
    source_path,
    validator_key,
)


def stat_key(stat):
    return json.dumps(fingerprint(stat), separators=(",", ":"))


class JobStore:
    def __init__(self, root):
        self.path = Path(root) / "Database" / "automation.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, variant TEXT NOT NULL,
                size INTEGER NOT NULL, modified_ns INTEGER NOT NULL,
                stop_after TEXT, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                project TEXT, log TEXT, error TEXT, created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL, UNIQUE(source, variant))""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            for name in ("source_sha256", "fingerprint_json", "duplicate_of"):
                if name not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {name} TEXT")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS jobs_content_variant
                ON jobs(source_sha256,variant) WHERE source_sha256 IS NOT NULL AND status!='duplicate'""")
            db.execute("""CREATE TABLE IF NOT EXISTS source_checks (
                source TEXT PRIMARY KEY, fingerprint_json TEXT NOT NULL,
                sha256 TEXT NOT NULL, probe_key TEXT NOT NULL, probe_json TEXT NOT NULL,
                processing_key TEXT, checked_utc TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS decoded_sources (
                sha256 TEXT NOT NULL, decoder_key TEXT NOT NULL, receipt_json TEXT NOT NULL,
                checked_utc TEXT NOT NULL, PRIMARY KEY(sha256,decoder_key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS decode_checkpoints (
                sha256 TEXT NOT NULL, decoder_key TEXT NOT NULL, policy_key TEXT NOT NULL,
                ordinal INTEGER NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
                receipt_json TEXT NOT NULL, checked_utc TEXT NOT NULL,
                PRIMARY KEY(sha256,decoder_key,policy_key,ordinal))""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_failure(self, source, error):
        source = Path(source).expanduser().resolve()
        report = (
            self.path.parent.parent
            / "AutomationLogs/rejected-inputs"
            / (key(str(source))[:20] + ".json")
        )
        try:
            save(
                report,
                {
                    "source": str(source),
                    "status": "rejected",
                    "error": str(error),
                    "tool": error.tool,
                    "stderr": error.stderr,
                    "returncode": error.returncode,
                    "ffprobe_stderr": error.stderr if error.tool.lower() == "ffprobe" else "",
                    "ffprobe_returncode": error.returncode
                    if error.tool.lower() == "ffprobe"
                    else None,
                    "checked_utc": now(),
                },
            )
        except OSError as report_error:
            print(f"Could not save validation report: {report_error}", file=sys.stderr, flush=True)

    def inspect(self, source, *, details=False):
        try:
            return inspect_source(source, details=details)
        except SourceValidationError as error:
            self.record_failure(source, error)
            raise

    def admit_source(self, source, *, settled=True):
        """Only complete, unchanged successful checks enter the reusable cache."""
        try:
            from quality_checks import production_source

            production_source(source)
            source = source_path(source)
            before = source.stat()
            if settled and time.time() - before.st_mtime < 60:
                raise SourceValidationError(
                    f"Recording is still settling; wait before queueing: {source}",
                    tool="filesystem",
                )
            signature = stat_key(before)
            probe_key = validator_key("ffprobe")
            with self.connect() as db:
                cached = db.execute(
                    "SELECT * FROM source_checks WHERE source=?", (str(source),)
                ).fetchone()
            if (
                cached
                and cached["fingerprint_json"] == signature
                and cached["probe_key"] == probe_key
            ):
                if stat_key(source.stat()) != signature:
                    raise SourceValidationError(
                        f"Recording changed during validation: {source}", tool="filesystem"
                    )
                return {
                    "source": str(source),
                    "stat": before,
                    "fingerprint": signature,
                    "sha256": cached["sha256"],
                    "probe": json.loads(cached["probe_json"]),
                    "processing_key": cached["processing_key"],
                    "fresh_hash": False,
                }
            source, probed, document = inspect_source(source, details=True)
            if stat_key(probed) != signature:
                raise SourceValidationError(
                    f"Recording changed during validation: {source}", tool="filesystem"
                )
            sha = digest(source)
            if stat_key(source.stat()) != signature:
                raise SourceValidationError(
                    f"Recording changed during checksum scan: {source}", tool="filesystem"
                )
            with self.connect() as db:
                db.execute(
                    """INSERT INTO source_checks VALUES (?,?,?,?,?,NULL,?)
                    ON CONFLICT(source) DO UPDATE SET fingerprint_json=excluded.fingerprint_json,
                    sha256=excluded.sha256,probe_key=excluded.probe_key,probe_json=excluded.probe_json,
                    processing_key=NULL,checked_utc=excluded.checked_utc""",
                    (str(source), signature, sha, probe_key, json.dumps(document), now()),
                )
            return {
                "source": str(source),
                "stat": before,
                "fingerprint": signature,
                "sha256": sha,
                "probe": document,
                "processing_key": None,
                "fresh_hash": True,
            }
        except (OSError, SourceValidationError) as error:
            if not isinstance(error, SourceValidationError):
                error = SourceValidationError(str(error), tool="filesystem")
            self.record_failure(source, error)
            raise error

    @staticmethod
    def _duplicate(db, sha, variant, exclude=""):
        return db.execute(
            """SELECT * FROM jobs WHERE source_sha256=? AND variant=?
            AND id!=? AND status!='duplicate' ORDER BY created_utc,id LIMIT 1""",
            (sha, variant, exclude),
        ).fetchone()

    def prior_project(self, source, sha, variant):
        """Recognize projects that predate the queue without migrating their files."""
        from start import project_for

        root = self.path.parent.parent
        for manifest in sorted((root / "Projects/V2").glob("*/manifest.json")):
            try:
                document = json.loads(manifest.read_text(encoding="utf-8"))
                previous = Path(document["source"]).resolve()
                if document.get("source_sha256") != sha or previous == Path(source).resolve():
                    continue
                if variant == "main" or manifest.parent.name == project_for(previous, variant).name:
                    return manifest.parent
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return None

    def enqueue(self, source, variant="main", stop_after=None):
        from quality_checks import production_source

        production_source(source)
        proof = self.admit_source(source)
        source = Path(proof["source"])
        stat = proof["stat"]
        identity = key({"source": str(source), "variant": variant})[:20]
        prior_project = self.prior_project(source, proof["sha256"], variant)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if stat_key(source.stat()) != proof["fingerprint"]:
                raise SourceValidationError(
                    f"Recording changed before queue insertion: {source}", tool="filesystem"
                )
            prior = db.execute(
                "SELECT * FROM jobs WHERE source=? AND variant=?", (str(source), variant)
            ).fetchone()
            if prior:
                if (prior["size"], prior["modified_ns"]) != (stat.st_size, stat.st_mtime_ns) or (
                    prior["source_sha256"] and prior["source_sha256"] != proof["sha256"]
                ):
                    raise SourceValidationError(
                        f"Source changed since enqueue; use a new filename: {source}",
                        tool="filesystem",
                    )
                canonical = (
                    db.execute("SELECT * FROM jobs WHERE id=?", (prior["duplicate_of"],)).fetchone()
                    if prior["duplicate_of"]
                    else prior
                )
                result = dict(canonical)
                result.update(duplicate_submission=True, submitted_source=str(source))
                return result
            duplicate = self._duplicate(db, proof["sha256"], variant)
            if duplicate:
                result = dict(duplicate)
                result.update(duplicate_submission=True, submitted_source=str(source))
                return result
            if prior_project:
                return {
                    "id": None,
                    "status": "existing_project",
                    "project": str(prior_project),
                    "source_sha256": proof["sha256"],
                    "duplicate_submission": True,
                    "submitted_source": str(source),
                    "message": "Identical recording already has a project; resume that project explicitly",
                }
            db.execute(
                """INSERT INTO jobs
                (id,source,variant,size,modified_ns,stop_after,status,created_utc,updated_utc,source_sha256,fingerprint_json)
                VALUES (?,?,?,?,?,?,'queued',?,?,?,?)""",
                (
                    identity,
                    str(source),
                    variant,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stop_after,
                    now(),
                    now(),
                    proof["sha256"],
                    proof["fingerprint"],
                ),
            )
        return self.get(identity)

    def processing_source(self, job, *, expected_sha=None):
        """Verify queued identity and a full decode before planning or speech."""
        try:
            source = source_path(job["source"])
            before = source.stat()
            if (before.st_size, before.st_mtime_ns) != (job["size"], job["modified_ns"]):
                raise SourceValidationError(
                    f"Source changed since enqueue: {source}", tool="filesystem"
                )
            if job.get("fingerprint_json") and job["fingerprint_json"] != stat_key(before):
                raise SourceValidationError(
                    f"Source metadata changed since enqueue: {source}", tool="filesystem"
                )
            proof = self.admit_source(source, settled=False)
            expected = job.get("source_sha256") or expected_sha
            if expected and proof["sha256"] != expected:
                raise SourceValidationError(
                    f"Source checksum changed since enqueue/project creation: {source}",
                    tool="checksum",
                )
            decoder = validator_key("ffmpeg")
            receipt_key = key({"sha256": proof["sha256"], "decoder": decoder})
            if proof["processing_key"] != receipt_key and not proof["fresh_hash"]:
                if digest(source) != proof["sha256"]:
                    raise SourceValidationError(
                        f"Source checksum changed since enqueue: {source}", tool="checksum"
                    )
            if stat_key(source.stat()) != proof["fingerprint"]:
                raise SourceValidationError(
                    f"Source changed while verifying checksum: {source}", tool="filesystem"
                )
            # Migrate old queue entries lazily, retaining IDs, attempts and history.
            # An old duplicate is recorded as such rather than launching a second job.
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                duplicate = self._duplicate(db, proof["sha256"], job["variant"], job["id"])
                if duplicate:
                    db.execute(
                        """UPDATE jobs SET status='duplicate',source_sha256=?,fingerprint_json=?,
                        duplicate_of=?,error=?,updated_utc=? WHERE id=? AND status='running'""",
                        (
                            proof["sha256"],
                            proof["fingerprint"],
                            duplicate["id"],
                            "Duplicate recording; canonical job retained",
                            now(),
                            job["id"],
                        ),
                    )
                    proof["duplicate_of"] = duplicate["id"]
                    return proof
                updated = db.execute(
                    """UPDATE jobs SET source_sha256=?,fingerprint_json=?,updated_utc=?
                    WHERE id=? AND status='running'""",
                    (proof["sha256"], proof["fingerprint"], now(), job["id"]),
                )
                if updated.rowcount != 1:
                    raise RuntimeError("Job is no longer claimed by the worker")
            prior_project = self.prior_project(source, proof["sha256"], job["variant"])
            if prior_project:
                raise SourceValidationError(
                    f"Identical recording already belongs to {prior_project}; resume that project explicitly",
                    tool="duplicate",
                )
            if proof["processing_key"] != receipt_key:
                with self.connect() as db:
                    decoded = db.execute(
                        "SELECT 1 FROM decoded_sources WHERE sha256=? AND decoder_key=?",
                        (proof["sha256"], decoder),
                    ).fetchone()
                if not decoded:
                    receipt = decode_source(source, proof["probe"])
                    if stat_key(source.stat()) != proof["fingerprint"]:
                        raise SourceValidationError(
                            f"Source changed during decode: {source}", tool="filesystem"
                        )
                    with self.connect() as db:
                        db.execute(
                            "INSERT OR IGNORE INTO decoded_sources VALUES (?,?,?,?)",
                            (proof["sha256"], decoder, json.dumps(receipt), now()),
                        )
                if stat_key(source.stat()) != proof["fingerprint"]:
                    raise SourceValidationError(
                        f"Source changed after decode: {source}", tool="filesystem"
                    )
                with self.connect() as db:
                    db.execute(
                        "UPDATE source_checks SET processing_key=? WHERE source=? AND fingerprint_json=? AND sha256=?",
                        (receipt_key, str(source), proof["fingerprint"], proof["sha256"]),
                    )
            return proof
        except (OSError, SourceValidationError) as error:
            if not isinstance(error, SourceValidationError):
                error = SourceValidationError(str(error), tool="filesystem")
            self.record_failure(job["source"], error)
            raise error

    def get(self, identity):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown queue job: {identity}")
        return dict(row)

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created_utc,id")]

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id FROM jobs WHERE status='queued' ORDER BY created_utc,id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET status='running',attempts=attempts+1,error=NULL,updated_utc=? WHERE id=?",
                (now(), row["id"]),
            )
        return self.get(row["id"])

    def claim_id(self, identity):
        """Claim one explicitly selected batch item; never drain unrelated jobs."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "UPDATE jobs SET status='running',attempts=attempts+1,error=NULL,updated_utc=? WHERE id=? AND status='queued'",
                (now(), identity),
            )
            if result.rowcount != 1:
                return None
        return self.get(identity)

    def finish(self, identity, status, *, project=None, log=None, error=None):
        if status not in {"needs_attention", "planned", "voiced", "ready_for_review", "duplicate"}:
            raise ValueError("Invalid job outcome")
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET status=?,project=COALESCE(?,project),log=COALESCE(?,log),error=?,updated_utc=? WHERE id=?",
                (
                    status,
                    str(project) if project else None,
                    str(log) if log else None,
                    error,
                    now(),
                    identity,
                ),
            )

    def recover_interrupted(self):
        with self.connect() as db:
            return db.execute(
                "UPDATE jobs SET status='needs_attention',error=?,updated_utc=? WHERE status='running'",
                (
                    "Worker interrupted. Inspect project and logs; explicit --retry-job required. No automatic speech retry.",
                    now(),
                ),
            ).rowcount

    def retry(self, identity, stop_after=None):
        original = self.get(identity)
        if original["status"] not in {"needs_attention", "planned", "voiced"}:
            raise ValueError("Only stopped, planned or voiced jobs can be explicitly resumed")
        stat = Path(original["source"]).stat()
        if (stat.st_size, stat.st_mtime_ns) != (original["size"], original["modified_ns"]):
            raise ValueError(
                "Source changed since enqueue; retain the original or use a new filename"
            )
        if original["fingerprint_json"] and stat_key(stat) != original["fingerprint_json"]:
            raise ValueError("Source metadata changed since enqueue")
        proof = self.admit_source(original["source"])
        if original["source_sha256"] and original["source_sha256"] != proof["sha256"]:
            raise SourceValidationError("Source checksum changed since enqueue", tool="checksum")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM jobs WHERE id=?", (identity,)).fetchone()
            if (
                dict(current) != original
                or stat_key(Path(original["source"]).stat()) != proof["fingerprint"]
            ):
                raise ValueError("Job/source changed while preparing explicit resume")
            duplicate = self._duplicate(db, proof["sha256"], original["variant"], identity)
            db.execute(
                """UPDATE jobs SET status=?,stop_after=?,error=NULL,source_sha256=?,fingerprint_json=?,duplicate_of=?,updated_utc=? WHERE id=?""",
                (
                    "duplicate" if duplicate else "queued",
                    stop_after,
                    proof["sha256"],
                    proof["fingerprint"],
                    duplicate["id"] if duplicate else None,
                    now(),
                    identity,
                ),
            )
        return self.get(identity)
