"""Conservative waveform-owned narration boundaries and coherent master gain."""

import json
import math
from pathlib import Path
import subprocess
import numpy as np

POLICY = "quiet-boundaries-v1"


def read_audio(path, rate=48000):
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    )
    return np.frombuffer(result.stdout, np.float32).copy()


def level(samples):
    return 20 * math.log10(
        max(float(np.sqrt(np.mean(np.asarray(samples, dtype=float) ** 2))), 1e-10)
    )


def boundary_level(samples, sample, rate=48000, width=0.02):
    half = round(width * rate / 2)
    return level(samples[max(0, sample - half) : min(len(samples), sample + half)])


def safe_boundaries(samples, spans, rate=48000):
    cuts = [0.0]
    diagnostics = []
    for i in range(len(spans) - 1):
        left, right = spans[i][1], spans[i + 1][0]
        original = (left + right) / 2
        before = boundary_level(samples, round(original * rate), rate)
        chosen = original
        if before > -48:
            # Find a sustained quiet run, not a short valley inside a trailing
            # /s/, /ts/ or plosive release. Never gate or de-ess spoken samples.
            step = round(0.002 * rate)
            half = round(0.006 * rate)
            points = list(range(round((left + 0.015) * rate), round((right - 0.02) * rate), step))
            runs = []
            current = []
            for sample in points:
                if level(samples[max(0, sample - half) : min(len(samples), sample + half)]) <= -48:
                    current.append(sample)
                else:
                    if current:
                        runs.append(current)
                    current = []
            if current:
                runs.append(current)
            runs = [run for run in runs if len(run) * step >= round(0.012 * rate)]
            if not runs:
                raise RuntimeError(
                    f"No safe quiet boundary between narration lines {i + 1} and {i + 2}; preserve audio and review timings"
                )
            selected = max(runs, key=lambda run: (len(run), -abs(np.mean(run) / rate - original)))
            midpoint = int(round((selected[0] + selected[-1]) / 2))
            radius = round(0.001 * rate)
            lo = max(selected[0], midpoint - radius)
            hi = min(selected[-1] + 1, midpoint + radius + 1)
            chosen = (lo + int(np.argmin(np.abs(samples[lo:hi])))) / rate
        after = boundary_level(samples, round(chosen * rate), rate)
        cuts.append(chosen)
        diagnostics.append(
            {
                "line_boundary": i + 1,
                "old_seconds": original,
                "new_seconds": chosen,
                "old_boundary_dbfs": before,
                "new_boundary_dbfs": after,
                "moved": abs(chosen - original) > 1 / rate,
            }
        )
    cuts.append(len(samples) / rate)
    return cuts, diagnostics


def quiet_edge_fade(samples, rate=48000, milliseconds=2):
    result = samples.copy()
    count = min(round(rate * milliseconds / 1000), len(result) // 2)
    if count < 1:
        return result
    # Only work in already quiet edge handles. Real consonants are untouched.
    envelope = np.sin(np.linspace(0, np.pi / 2, count)) ** 2
    if level(result[: max(count, round(0.01 * rate))]) <= -45:
        result[:count] *= envelope
    if level(result[-max(count, round(0.01 * rate)) :]) <= -45:
        result[-count:] *= envelope[::-1]
    return result


def master_gain(path, target=-16.0, peak=-1.5):
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostdin",
            "-i",
            str(path),
            "-af",
            f"loudnorm=I={target}:TP={peak}:LRA=9:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    start = result.stderr.rfind("{")
    end = result.stderr.rfind("}")
    measured = json.loads(result.stderr[start : end + 1])
    loudness = float(measured["input_i"])
    true_peak = float(measured["input_tp"])
    if not math.isfinite(loudness + true_peak):
        raise RuntimeError("Cannot normalize silent/nonfinite narration master")
    gain = min(float(target) - loudness, float(peak) - true_peak)
    return {
        "policy": "single-linear-master-gain-v1",
        "gain_db": gain,
        "input_lufs": loudness,
        "input_true_peak_db": true_peak,
        "target_lufs": target,
        "true_peak_ceiling_db": peak,
        "note": "Constant gain; no de-essing, denoising, gating or speech time stretching",
    }


def export_segment(samples, path, rate=48000):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-n",
            "-f",
            "f32le",
            "-ar",
            str(rate),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        input=np.asarray(samples, np.float32).tobytes(),
        check=True,
    )
