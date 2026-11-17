#!/usr/bin/env python3
"""Inspect long gameplay without transcoding the original: timestamped contact-sheet ZIP.

No database mutations, source copies, audio-generation, uploads or deletions.
"""

from __future__ import annotations
import argparse, hashlib, json, math, os, shutil, sqlite3, subprocess, sys, time, zipfile
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def ffprobe(p):
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(p)],
        capture_output=True,
        text=True,
        check=True,
        timeout=90,
    )
    return json.loads(proc.stdout)


def signature(p):
    s = p.stat()
    info = {"path": str(p.resolve()), "size_bytes": s.st_size, "modified_ns": s.st_mtime_ns}
    return info, hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()[:20]


def used(root, source):
    """Read only: existing V2 project manifests and editorial reservations, if present."""
    manifest_candidates = list((root / "Projects" / "V2").glob("*/manifest.json"))
    manifest_candidates += list((root / "Projects" / "Automated").glob("*/manifest.json"))
    hashes = set()
    project_matches = []
    for mf in manifest_candidates:
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            if Path(data.get("source", "")).resolve() == source.resolve():
                # Only trust SHA if the manifest's recorded source metadata still matches.
                stat = source.stat()
                if (
                    data.get("source_size_bytes") == stat.st_size
                    and data.get("source_modified_ns") == stat.st_mtime_ns
                ):
                    hashes.add(data.get("source_sha256", ""))
                project_matches.append(
                    {
                        "project": str(mf.parent),
                        "source_hash_known": bool(data.get("source_sha256")),
                    }
                )
        except (OSError, ValueError, TypeError, KeyError):
            pass
    ranges = []
    database = root / "Database" / "editorial_v2.sqlite3"
    if database.exists() and hashes:
        try:
            con = sqlite3.connect("file:" + str(database.resolve()) + "?mode=ro", uri=True)
            try:
                for h in hashes:
                    for p, a, b in con.execute(
                        "SELECT project,start,end FROM footage_reservations WHERE source_hash=?",
                        (h,),
                    ):
                        ranges.append(
                            {"project": p, "start": round(float(a), 3), "end": round(float(b), 3)}
                        )
            finally:
                con.close()
        except sqlite3.Error as exc:
            print("Warning: unavailable editorial database:", exc, file=sys.stderr)
    return {
        "matching_projects": project_matches,
        "reserved_v2_ranges": ranges,
        "note": "Legacy V1 range database is not included in this report; the existing editor checks it separately.",
    }


def storage_audit(root, source):
    """Quick read-only disk inventory. Same-size files are NOT proof of identical content."""
    inspected = 0
    files = []
    seen = set()
    for name in ("Sources", "ReviewCopies", "Projects", "ReadyForReview"):
        folder = root / name
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            inspected += 1
            if inspected > 100000:
                break
            try:
                if not path.is_file() or path.is_symlink() or path.suffix.lower() not in VIDEO_EXTS:
                    continue
                unique = str(path.resolve())
                if unique in seen:
                    continue
                seen.add(unique)
                st = path.stat()
                files.append({"path": str(path), "size_bytes": st.st_size})
            except (OSError, ValueError):
                continue
        if inspected > 100000:
            break
    files.sort(key=lambda x: x["size_bytes"], reverse=True)
    # Probe only big candidates to avoid expensive per-file decoding.
    for item in files[:20]:
        try:
            p = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nokey=1:noprint_wrappers=1",
                    item["path"],
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            item["duration_seconds"] = round(float(p.stdout.strip()), 2)
        except (ValueError, OSError, subprocess.SubprocessError):
            pass
    by_size = {}
    for item in files:
        by_size.setdefault(item["size_bytes"], []).append(item["path"])
    repeated = [
        {"size_bytes": size, "paths": paths[:25]}
        for size, paths in by_size.items()
        if size > 0 and len(paths) > 1
    ]
    return {
        "total_video_file_count": len(files),
        "aggregate_size_bytes": sum(x["size_bytes"] for x in files),
        "largest_video_files": files[:30],
        "same_size_groups_unverified": repeated[:20],
        "scan_truncated": inspected > 100000,
        "important": "Matching sizes or durations do not prove identical content. No video content was re-encoded or copied.",
    }


def make_sheet(source, out, start, seconds, idx, total, log):
    if out.is_file() and out.stat().st_size > 800:
        return "cached"
    interval = max(0.1, seconds / 16)
    # Timestamps remain on the recording clock even though input seeks to start.
    vf = (
        f"scale=320:180:force_original_aspect_ratio=decrease,pad=320:180:(ow-iw)/2:(oh-ih)/2,"
        f"setpts=PTS+{start:.6f}/TB,"
        f"drawtext=fontfile={FONT}:text='%{{pts\\:hms}}':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.75:x=4:y=4,"
        f"fps=1/{interval:.6f},tile=4x4"
    )
    temp = out.with_suffix(".partial.jpg")
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        f"{start:.6f}",
        "-t",
        f"{seconds:.6f}",
        "-i",
        str(source),
        "-an",
        "-vf",
        vf,
        "-frames:v",
        "1",
        "-update",
        "1",
        str(temp),
    ]
    with log.open("a", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    if proc.returncode or not temp.exists() or temp.stat().st_size < 800:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg could not create sheet {idx}/{total}. Inspect {log}")
    os.replace(temp, out)
    return "new"


def run(source, root, sheets, force=False):
    source = source.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in VIDEO_EXTS:
        raise ValueError("Recording missing or unsupported extension")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe required")
    if not Path(FONT).is_file():
        raise RuntimeError("Ubuntu DejaVuSans-Bold font missing")
    if not (4 <= sheets <= 64):
        raise ValueError("4 to 64 sheets supported")
    info, ident = signature(source)
    probe = ffprobe(source)
    duration = float(probe["format"]["duration"])
    if not math.isfinite(duration) or duration < 15:
        raise ValueError("Recording duration must be at least 15 sec")
    folder = root / "FootageIndex" / ident / f"review_{sheets}"
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / "ffmpeg.log"
    reviewed = []
    # 4x4 frames per sheet, sampled at equal time intervals. No source rewriting.
    for idx in range(sheets):
        start = duration * idx / sheets
        span = duration * (idx + 1) / sheets - start
        out = folder / f"sheet_{idx + 1:02d}.jpg"
        if force:
            out.unlink(missing_ok=True)
        status = make_sheet(source, out, start, span, idx + 1, sheets, log)
        print(
            f"[{idx + 1}/{sheets}] {start / 60:06.2f}–{(start + span) / 60:06.2f} min: {status}",
            flush=True,
        )
        reviewed.append(
            {
                "sheet": out.name,
                "start_seconds": round(start, 3),
                "end_seconds": round(start + span, 3),
            }
        )
    meta = {
        "recording": info,
        "duration_seconds": round(duration, 3),
        "duration_minutes": round(duration / 60, 2),
        "codec_streams": [
            {
                "codec_type": x.get("codec_type"),
                "codec_name": x.get("codec_name"),
                "width": x.get("width"),
                "height": x.get("height"),
                "avg_frame_rate": x.get("avg_frame_rate"),
            }
            for x in probe.get("streams", [])
        ],
        "contact_sheet_count": sheets,
        "frames_per_sheet": 16,
        "sampling_note": "Overview frames are sampled; fast events between frames may be missed.",
        "sheets": reviewed,
        "history": used(root, source),
        "storage_audit": storage_audit(root, source),
    }
    (folder / "recording_report.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    readme = (
        f"GamingShorts: {source.name}\nDuration: {duration / 60:.2f} minutes\n"
        f"{sheets} timestamped contact sheets, 16 frames each.\n"
        "Open sheet_01.jpg through the final sheet in order. Each frame displays the original video time.\n"
        "Upload the ZIP to ChatGPT for visual analysis. These are sampled frames, not the entire moving video.\n"
        "Existing source file is unchanged. No full-resolution proxy or transcoded copy was created.\n"
    )
    (folder / "README.txt").write_text(readme, encoding="utf-8")
    exports = root / "ReviewExports"
    exports.mkdir(parents=True, exist_ok=True)
    zipout = exports / f"Gameplay_Inspection_{ident}_{sheets}sheets.zip"
    tmp = zipout.with_suffix(".partial.zip")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as z:
        for name in ["README.txt", "recording_report.json"]:
            z.write(folder / name, arcname=name)
        for item in reviewed:
            z.write(folder / item["sheet"], arcname=item["sheet"])
    os.replace(tmp, zipout)
    print("\nINSPECTION EXPORT:", zipout, flush=True)
    print("Original recording: UNMODIFIED. Upload this ZIP to ChatGPT.", flush=True)
    return zipout


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True, help="Original recording")
    ap.add_argument("--root", type=Path, default=Path("/mnt/d/GamingShorts"))
    ap.add_argument(
        "--sheets", type=int, default=24, help="Number of 16-frame preview sheets (default 24)"
    )
    ap.add_argument("--refresh", action="store_true", help="Rebuild cached sheets intentionally")
    args = ap.parse_args()
    try:
        run(args.source, args.root, args.sheets, args.refresh)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        print("STOPPED:", e, file=sys.stderr)
        sys.exit(1)
