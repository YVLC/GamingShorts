"""Read-only owner verification; no uploader and no original source deletion."""

import json, os, re, urllib.request, urllib.parse
from pathlib import Path
from common import read, save, digest, now, state
import editorial


def validate_remote(item, video_id, channel_id, final):
    if item.get("id") != video_id or item.get("snippet", {}).get("channelId") != channel_id:
        raise ValueError("Video or channel identity mismatch")
    if item.get("status", {}).get("privacyStatus") != "public":
        raise ValueError("Video is not public yet")
    if (
        item.get("status", {}).get("uploadStatus") != "processed"
        or item.get("processingDetails", {}).get("processingStatus") != "succeeded"
    ):
        raise ValueError("YouTube processing has not succeeded")
    details = item.get("fileDetails", {})
    if (
        details.get("fileName") != final.name
        or int(details.get("fileSize", -1)) != final.stat().st_size
    ):
        raise ValueError("Owner file name/size do not match the approved local export")
    return True


def verify(project, video_id):
    import gaming_shorts as gs

    p = Path(project)
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Supply the 11-character YouTube video ID")
    if not gs.completed(p):
        raise ValueError("Current local render is not validated")
    q = read(p / "qc_report.json")
    approval = read(p / "approval.json")
    final = Path(q["output"])
    if approval["output_sha256"] != q["output_sha256"] or approval["input_key"] != q["input_key"]:
        raise ValueError("Approve the current export first")
    token = os.environ.get("YOUTUBE_ACCESS_TOKEN")
    channel = os.environ.get("YOUTUBE_CHANNEL_ID")
    if not token or not channel:
        raise RuntimeError(
            "Owner OAuth access token and channel ID required in YOUTUBE_ACCESS_TOKEN and YOUTUBE_CHANNEL_ID; never paste credentials into chat"
        )
    query = urllib.parse.urlencode(
        {"part": "snippet,status,processingDetails,fileDetails", "id": video_id}
    )
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/videos?" + query,
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    if len(data.get("items", [])) != 1:
        raise ValueError("YouTube did not return this owner video")
    validate_remote(data["items"][0], video_id, channel, final)
    validate_music_credit(data["items"][0], q.get("music", {}))
    evidence = {
        "video_id": video_id,
        "channel_id": channel,
        "output_sha256": digest(final),
        "input_key": q["input_key"],
        "verified_utc": now(),
        "status": "published",
        "verification": "owner API: public, processed, succeeded, matching filename and byte size; YouTube supplies no source SHA256",
    }
    with editorial.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS publications (project TEXT, output_sha256 TEXT, video_id TEXT UNIQUE, evidence_json TEXT, PRIMARY KEY(project,output_sha256))"
        )
        db.execute(
            "INSERT INTO publications VALUES (?,?,?,?) ON CONFLICT(project,output_sha256) DO UPDATE SET video_id=excluded.video_id,evidence_json=excluded.evidence_json",
            (str(p), q["output_sha256"], video_id, json.dumps(evidence)),
        )
    # Only after SQLite commit do we announce published.
    save(p / "publication.json", evidence)
    editorial.remember(p, "published")
    state(p, "published", **{k: v for k, v in evidence.items() if k != "status"})
    print("Verified public YouTube video: https://www.youtube.com/watch?v=" + video_id)


def cleanup(project, apply=False):
    """Remove only enumerated generated intermediates after a committed publication.
    Source recordings, narration, plans, DB, final export and sidecars are retained.
    """

    p = Path(project).resolve()
    q = read(p / "qc_report.json")
    final = Path(q["output"])
    if not final.is_file() or digest(final) != q["output_sha256"]:
        raise RuntimeError("Approved output missing or changed")
    with editorial.connect() as db:
        exists = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='publications'"
        ).fetchone()
        row = (
            db.execute(
                "SELECT evidence_json FROM publications WHERE project=? AND output_sha256=?",
                (str(p), q["output_sha256"]),
            ).fetchone()
            if exists
            else None
        )
    if not row:
        raise RuntimeError("No committed publication verification for this output; cleanup blocked")
    evidence = json.loads(row[0])
    if evidence["input_key"] != q["input_key"]:
        raise RuntimeError("Publication refers to a different render")
    folder = p / "Renders" / q["input_key"][:16]
    if (
        (p / "Renders").is_symlink()
        or folder.is_symlink()
        or not folder.resolve().is_relative_to(p)
    ):
        raise RuntimeError("Refusing render directory outside project or through symlink")
    original_source = Path(read(p / "manifest.json")["source"]).resolve()
    allowed = re.compile(
        r"(shot_\d+\.mp4|normalized_\d+\.wav|check_\d+\.wav|qc_(speech|music|mix)\.wav|speech\.wav|music\.wav|video\.mp4|candidate\.mp4)"
    )
    files = (
        [
            f
            for f in folder.iterdir()
            if f.is_file()
            and not f.is_symlink()
            and f.resolve() != original_source
            and allowed.fullmatch(f.name)
        ]
        if folder.exists()
        else []
    )
    print(
        ("Deleting" if apply else "Dry run: would delete"),
        len(files),
        "generated intermediate files;",
        sum(f.stat().st_size for f in files),
        "bytes",
    )
    if apply:
        for f in files:
            f.unlink()
        save(
            p / "cleanup.json",
            {"utc": now(), "publication": evidence, "removed": [str(f) for f in files]},
        )
    return files


def validate_music_credit(item, music):
    """Read-only publication checks reject missing required music credit."""
    if not music.get("path") or not music.get("attribution_required"):
        return
    credit = music.get("attribution", "").strip()
    description = item.get("snippet", {}).get("description", "")
    if not credit or any(line.strip() not in description for line in credit.splitlines() if line.strip()):
        raise ValueError("Published description lacks required music attribution")
