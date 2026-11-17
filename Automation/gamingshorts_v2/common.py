from __future__ import annotations
import contextlib, datetime, hashlib, json, os, subprocess, tempfile, time
from contextvars import ContextVar
from pathlib import Path

VERSION = "2.1.0"
_source_receipts = ContextVar("verified_source_receipts", default={})
HERE = Path(__file__).resolve().parent
DEFAULTS = {
    "root": "/mnt/d/GamingShorts",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "crf": 22,
    "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "music": "music/original_tension.mp3",
    "voice_id": "f49763c1a284420b8f25f16472d8738e",
    "voice_model": "heygen-voice-1-turbo-free",
    "caption_mode": "phrase",
    "alignment_model": "base.en",
    "encoder": "libx264",
    "music_rotation": False,
    "min_seconds": 25,
    "max_seconds": 40,
    "music_lufs": -30,
    "voice_lufs": -16,
    "codex_timeout_seconds": 1200,
    "media_timeout_seconds": 3600,
}


def config():
    c = dict(DEFAULTS)
    p = HERE / "config.json"
    if p.exists():
        c.update(read(p))
    c["root"] = os.environ.get("GAMING_SHORTS_HOME", c["root"])
    root = Path(c["root"]).expanduser()
    if not root.is_absolute():
        root = HERE / root
    c["root"] = str(root.resolve())
    if c.get("caption_mode") not in ("phrase", "karaoke"):
        raise ValueError("caption_mode must be phrase or karaoke")
    if c["voice_model"] != "heygen-voice-1-turbo-free":
        raise ValueError("Only the free speech model is allowed.")
    if (
        not 144 <= c["width"] <= 2160
        or not 256 <= c["height"] <= 3840
        or c["width"] % 2
        or c["height"] % 2
    ):
        raise ValueError("Invalid even output dimensions")
    return c


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p, obj):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def digest(p):
    receipt = _source_receipts.get().get(str(Path(p).resolve()))
    if receipt:
        from source_validation import fingerprint
        if fingerprint(Path(p).stat()) != tuple(receipt["fingerprint"]):
            raise ValueError("Verified source changed during rendering")
        return receipt["sha256"]
    h = hashlib.sha256()
    checked = 0
    last = time.monotonic()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
            checked += len(b)
            if time.monotonic() - last >= 10:
                print(f"Checksum progress: {checked // (1024 * 1024)} MiB read", flush=True)
                last = time.monotonic()
    return h.hexdigest()


@contextlib.contextmanager
def verified_source_receipts(receipts):
    """Scoped V3 originals only, after strict integrity verification; audio/code hashes stay fresh."""
    token = _source_receipts.set(receipts)
    try:
        yield
    finally:
        _source_receipts.reset(token)


def key(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


@contextlib.contextmanager
def locked(path):
    import fcntl

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another GamingShorts process is running. Wait for it to finish.")
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def run(cmd, *, cwd=None, logfile=None, timeout=None):
    cmd = [str(x) for x in cmd]
    if logfile:
        with Path(logfile).open("a", encoding="utf-8") as f:
            f.write("\n" + now() + " " + cmd[0] + "\n")
            f.flush()
            p = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=timeout or config()["media_timeout_seconds"],
            )
        if p.returncode:
            raise RuntimeError(
                f"{cmd[0]} failed ({p.returncode}); see {logfile}\n"
                + Path(logfile).read_text(errors="replace")[-1800:]
            )
    else:
        subprocess.run(
            cmd, cwd=cwd, check=True, timeout=timeout or config()["media_timeout_seconds"]
        )


def state(project, stage, **details):
    save(
        Path(project) / "state.json",
        {"version": VERSION, "stage": stage, "updated_utc": now(), **details},
    )


def configured_source():
    """Resolve the selected original relative to the shared workspace on either OS."""
    c = config()
    value = c.get("active_source")
    return (Path(c["root"]) / value).resolve() if value else None
