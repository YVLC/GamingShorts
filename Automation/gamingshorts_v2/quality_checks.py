"""Motion-aware cadence and source-relative checks; no frame interpolation."""

from fractions import Fraction
from pathlib import Path
import subprocess

POLICY = "cadence-v1"


def rate(value):
    try:
        number = Fraction(str(value))
        return number if number > 0 else Fraction(0)
    except (ValueError, ZeroDivisionError):
        return Fraction(0)


def cadence_from_frames(frames, fps):
    import numpy as np

    data = np.asarray(frames, dtype=np.float32)
    if len(data) < 3:
        return {"status": "insufficient_frames", "frames": len(data), "active_windows": 0}
    delta = np.abs(np.diff(data, axis=0)).reshape(len(data) - 1, -1).mean(axis=1)
    positive = delta[delta > 0.02]
    threshold = (
        max(0.04, min(0.35, float(np.percentile(positive, 90)) * 0.12)) if len(positive) else 0.04
    )
    changes = delta >= threshold
    stride = max(1, round(float(fps)))
    active = []
    for start in range(0, len(delta), stride):
        block = delta[start : start + stride]
        if len(block) < stride * 0.4:
            continue
        # Static/near-static scenes have no sustained displacement and aren't
        # assigned a fake low "frame rate" merely for not changing visually.
        subset = data[start : min(len(data), start + stride + 1)]
        positions = np.linspace(0, len(subset) - 1, min(5, len(subset)), dtype=int)
        displacement = max(
            float(np.abs(subset[position] - subset[0]).mean()) for position in positions
        )
        if np.percentile(block, 90) > 0.15 and displacement > max(
            0.5, float(np.median(block)) * 1.4
        ):
            active.append(float(np.count_nonzero(block >= threshold) / (len(block) / float(fps))))
    updates = float(np.count_nonzero(changes) / (len(delta) / float(fps)))
    repeats = float(np.mean(~changes))
    status = "static_or_low_motion" if not active else "motion"
    return {
        "status": status,
        "frames": len(data),
        "nominal_fps": float(fps),
        "threshold": threshold,
        "mean_adjacent_difference": float(delta.mean()),
        "near_duplicate_fraction": repeats,
        "active_windows": len(active),
        "active_updates_per_second": float(np.median(active)) if active else None,
        "updates_per_second_all": updates,
        "cadence_limited": bool(
            active and np.median(active) < float(fps) * 0.55 and repeats > 0.45
        ),
    }


def measure_cadence(path, start, seconds, fps, *, roi=None):
    import numpy as np

    # Analyze the central picture above the caption band; typography must not
    # manufacture apparent gameplay motion. No fps filter changes the sample stream.
    crop = f"crop=iw*{roi[2]}:ih*{roi[3]}:iw*{roi[0]}:ih*{roi[1]}," if roi else ""
    filters = crop + "scale=96:54:flags=area,format=gray"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "2",
        "-ss",
        str(start),
        "-i",
        str(path),
        "-t",
        str(seconds),
        "-an",
        "-vf",
        filters,
        "-fps_mode",
        "passthrough",
        "-pix_fmt",
        "gray",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"Cadence decode failed: {result.stderr.decode(errors='replace')}")
    raw = np.frombuffer(result.stdout, np.uint8)
    if raw.size % (96 * 54):
        raise RuntimeError("Incomplete cadence frame stream")
    return cadence_from_frames(raw.reshape(-1, 54, 96), fps)


def compare_cadence(source, output):
    if not source.get("active_windows"):
        return {"status": "static_or_low_motion", "error": None}
    expected = source["active_updates_per_second"]
    actual = output.get("active_updates_per_second") or 0.0
    # Low-motion classification can straddle its displacement cutoff after
    # scaling/encoding even when every foreground frame still updates. Use the
    # measured source-relative updates, differences and duplicate fraction to
    # distinguish that case from a frozen or cadence-degraded foreground. The
    # caller's matched foreground ROI excludes generated captions/blur borders.
    if not output.get('active_windows') and source.get('mean_adjacent_difference',0)>.005:
        observed=output.get('updates_per_second_all',0)
        difference_ratio=output.get('mean_adjacent_difference',0)/source['mean_adjacent_difference']
        duplicates=output.get('near_duplicate_fraction',1)
        if observed>=expected*.70 and difference_ratio>=.70 and duplicates<=min(.25,source.get('near_duplicate_fraction',0)+.10):
            return {'status':'pass','source_active_updates':expected,'output_measured_updates':observed,
                    'difference_ratio':difference_ratio,'output_near_duplicate_fraction':duplicates,
                    'classification':'low_motion_with_matching_foreground_frame_updates','error':None}
    degraded = actual < expected * 0.70
    return {
        "status": "failed" if degraded else "pass",
        "source_active_updates": expected,
        "output_active_updates": actual,
        "error": f"Motion cadence fell from {expected:.2f} to {actual:.2f} visual updates/s"
        if degraded
        else None,
    }


def production_source(path):
    forbidden = {"reviewcopies", "reviewexports", "planningframes", "footageindex"}
    if forbidden.intersection(part.lower() for part in Path(path).parts):
        from source_validation import SourceValidationError

        raise SourceValidationError(
            f"Inspection proxy cannot be used as a production source: {path}. Relink to the original or a verified original-fragment bundle.",
            tool="provenance",
        )
