"""Real timed encoder trials. No automatic claim that WSL exposes Intel QSV."""

from pathlib import Path
import subprocess, time
from common import save, now


def run(source, out):
    import gaming_shorts as gs

    source = Path(source).resolve()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    secs = min(10, gs.duration(source))
    rows = []
    for w, h in ((720, 1280), (1080, 1920)):
        for encoder in ("libx264", "h264_qsv"):
            label = f"{encoder}_{w}"
            dest = out / (label + ".mp4")
            args = (
                ["-threads", "2", "-preset", "veryfast", "-crf", "22"]
                if encoder == "libx264"
                else ["-preset", "veryfast", "-global_quality", "22"]
            )
            cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-t",
                str(secs),
                "-an",
                "-vf",
                f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=nv12",
                "-c:v",
                encoder,
                *args,
                str(dest),
            ]
            print("Benchmark:", label, flush=True)
            t = time.perf_counter()
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                elapsed = time.perf_counter() - t
                (out / (label + ".log")).write_text(r.stderr)
                row = {
                    "encoder": encoder,
                    "width": w,
                    "height": h,
                    "seconds": elapsed,
                    "status": "failed",
                    "log": str(out / (label + ".log")),
                }
                if r.returncode == 0:
                    check = subprocess.run(
                        ["ffmpeg", "-v", "error", "-xerror", "-i", str(dest), "-f", "null", "-"],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if check.returncode == 0:
                        row.update(
                            status="passed",
                            speed_x=secs / elapsed,
                            size_bytes=dest.stat().st_size,
                            output=str(dest),
                        )
                rows.append(row)
            except subprocess.TimeoutExpired:
                rows.append({"encoder": encoder, "width": w, "height": h, "status": "timeout"})
    report = {
        "utc": now(),
        "source": str(source),
        "duration": secs,
        "runs": rows,
        "limitations": "Timing includes decode, resize and encode, not the full pipeline. CRF 22 and QSV quality 22 are not equivalent visual quality. Compare samples manually. A failed QSV run is not a CPU fallback result.",
    }
    save(out / "benchmark.json", report)
    print("Benchmark report:", out / "benchmark.json")
    return report
