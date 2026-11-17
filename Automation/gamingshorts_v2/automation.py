"""One durable queue worker around the existing versioned workflow."""

from pathlib import Path
import json
import math
import subprocess
import sys
import time

from common import HERE, locked, read, configured_source
from job_store import JobStore
from source_validation import MEDIA, SourceValidationError, source_path
from source_validation import fingerprint as file_fingerprint
import gaming_shorts as gs


def validate_source(path):
    return source_path(path)


class Discovery:
    """Require unchanged size/mtime across a settling window, including after restart."""

    def __init__(self, settle_seconds=60):
        if not math.isfinite(settle_seconds) or settle_seconds < 0:
            raise ValueError("Invalid settling window")
        self.settle_seconds = settle_seconds
        self.observed = {}
        self.rejected = {}
        self.admitted = {}

    def scan(self, store, variant="main", stop_after=None):
        from start import project_for, slug

        folder = gs.ROOT / "Sources"
        folder.mkdir(parents=True, exist_ok=True)
        clock = time.monotonic()
        present = set()
        added = []
        known = {(job["source"], job["variant"]) for job in store.list()}
        for source in sorted(folder.iterdir()):
            if source.is_symlink() or not source.is_file() or source.suffix.lower() not in MEDIA:
                continue
            if source.resolve() == configured_source():
                continue  # Explicit full-game workflow owns this configured original.
            present.add(source)
            try:
                stat = source.stat()
            except OSError as error:
                print(
                    f"Input unavailable; not queued: {source}: {error}", file=sys.stderr, flush=True
                )
                continue
            fingerprint = file_fingerprint(stat)
            previous = self.observed.get(source)
            if previous is None or previous[0] != fingerprint:
                self.observed[source] = (fingerprint, clock)
                self.rejected.pop(source, None)
                self.admitted.pop((source, variant), None)
                continue
            if (
                clock - previous[1] < self.settle_seconds
                or time.time() - stat.st_mtime < self.settle_seconds
            ):
                continue
            # Existing projects need explicit enqueue/resume; never rediscover rejection,
            # approval, uncertain speech, or an older workflow's source automatically.
            if (project_for(source, variant) / "manifest.json").exists():
                continue
            if (gs.ROOT / "Projects" / "Automated" / slug(source.name)).exists():
                continue
            if (str(source.resolve()), variant) in known:
                continue
            if self.admitted.get((source, variant)) == fingerprint:
                continue
            if self.rejected.get(source) == fingerprint:
                continue
            try:
                job = store.enqueue(source, variant, stop_after)
            except (SourceValidationError, OSError) as error:
                self.rejected[source] = fingerprint
                print(f"Rejected input; not queued: {error}", file=sys.stderr, flush=True)
                continue
            known.add((str(source.resolve()), variant))
            self.admitted[(source, variant)] = fingerprint
            if job.get("duplicate_submission"):
                print(
                    f"Duplicate recording; existing work retained: {job.get('project') or job['id']} | {source}",
                    flush=True,
                )
            else:
                added.append(job["id"])
        self.observed = {path: entry for path, entry in self.observed.items() if path in present}
        self.rejected = {path: entry for path, entry in self.rejected.items() if path in present}
        self.admitted = {
            entry: value for entry, value in self.admitted.items() if entry[0] in present
        }
        return added


def run_job(store, job, runner=None):
    """A failed attempt always requires attention, even if the process returned zero."""
    from start import prepare, project_for

    runner = runner or subprocess.run
    project = project_for(Path(job["source"]), job["variant"])
    log = gs.ROOT / "AutomationLogs" / f"{job['id']}-{job['attempts']:03d}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        source = validate_source(job["source"])
        stat = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != (job["size"], job["modified_ns"]):
            raise ValueError("Source changed since enqueue; refusing to process different bytes")
        # The child obtains the workflow lock for the actual pipeline. Preparation
        # is also protected so manual commands and the queue share the same guard.
        with locked(gs.ROOT / "Database" / ".workflow_v2.lock"):
            if (project / "state.json").exists():
                stage = read(project / "state.json").get("stage")
                if stage in {"approved", "published", "rejected"}:
                    raise ValueError(f"Project is {stage}; use its explicit review/replan commands")
            expected_sha = (
                read(project / "manifest.json").get("source_sha256")
                if (project / "manifest.json").exists()
                else None
            )
            proof = store.processing_source(job, expected_sha=expected_sha)
            if proof.get("duplicate_of"):
                print(
                    f"{job['id']}: duplicate of {proof['duplicate_of']}; existing project preserved",
                    flush=True,
                )
                return
            prepare(source, job["variant"], verified_source=proof)
        command = [sys.executable, str(HERE / "start.py"), "--project", str(project)]
        if job["stop_after"]:
            command += ["--stop-after", job["stop_after"]]
        # Keep the job running while recording context; never expose a retryable
        # state between preparation and launching the child.
        with store.connect() as db:
            db.execute(
                "UPDATE jobs SET project=?,log=? WHERE id=?", (str(project), str(log), job["id"])
            )
        with log.open("x", encoding="utf-8") as stream:
            result = runner(command, cwd=HERE, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"Workflow stopped with exit code {result.returncode}; see {log}")
        if job["stop_after"] == "plan":
            if not (project / "edit_plan.json").is_file():
                raise RuntimeError("Child returned without a saved plan")
            outcome = "planned"
        elif job["stop_after"] == "voice":
            if not (project / "active_voice.json").is_file():
                raise RuntimeError("Child returned without verified narration")
            outcome = "voiced"
        else:
            if not gs.completed(project):
                raise RuntimeError("Child returned without a current validated final output")
            outcome = "ready_for_review"
        store.finish(job["id"], outcome, project=project, log=log)
        print(f"{job['id']}: {outcome} | {project}", flush=True)
    except (Exception, KeyboardInterrupt) as error:
        store.finish(job["id"], "needs_attention", project=project, log=log, error=str(error))
        with log.open("a", encoding="utf-8") as stream:
            stream.write(str(error) + "\n")
        print(f"{job['id']}: needs_attention | {error}", flush=True)
        if isinstance(error, KeyboardInterrupt):
            raise


def work(
    store,
    *,
    watch=False,
    poll_seconds=30,
    settle_seconds=60,
    variant="main",
    stop_after=None,
    runner=None,
):
    if not math.isfinite(poll_seconds) or not 5 <= poll_seconds <= 60:
        raise ValueError("Poll interval must be between 5 and 60 seconds")
    if not math.isfinite(settle_seconds) or settle_seconds < 60:
        raise ValueError("Settling window must be at least 60 seconds")
    with locked(gs.ROOT / "Database" / ".automation.lock"):
        recovered = store.recover_interrupted()
        if recovered:
            print(f"Stopped {recovered} interrupted jobs for explicit recovery", flush=True)
        discovery = Discovery(settle_seconds)
        while True:
            if watch:
                for identity in discovery.scan(store, variant, stop_after):
                    print("Queued stable recording:", identity, flush=True)
            try:
                with locked(gs.ROOT / "Database" / ".workflow_v2.lock"):
                    pass
            except RuntimeError:
                print("Workflow busy; queued jobs remain untouched", flush=True)
                if not watch:
                    return
                time.sleep(poll_seconds)
                continue
            job = store.claim()
            if job:
                run_job(store, job, runner)
                continue
            if not watch:
                return
            time.sleep(poll_seconds)


def handle(args):
    store = JobStore(gs.ROOT)
    if args.queue:
        print(json.dumps(store.list(), indent=2))
    elif args.enqueue:
        if args.source is None:
            raise ValueError("--enqueue requires --source")
        source = validate_source(args.source)
        if time.time() - source.stat().st_mtime < args.settle_seconds:
            raise ValueError(
                "Recording changed recently; wait for copying to finish or use --watch"
            )
        print(json.dumps(store.enqueue(source, args.variant, args.stop_after), indent=2))
    elif args.retry_job:
        print(json.dumps(store.retry(args.retry_job, args.stop_after), indent=2))
    else:
        work(
            store,
            watch=args.watch,
            poll_seconds=args.poll_seconds,
            settle_seconds=args.settle_seconds,
            variant=args.variant,
            stop_after=args.stop_after,
        )
