#!/usr/bin/env python3
"""Free HeyGen speech handoff, verified downloads and phrase-based audio splitting."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from common import digest, read, save as json_save_atomic

import gaming_shorts as gs


VOICE_ID = "f49763c1a284420b8f25f16472d8738e"  # Garret — Bold & Persuasive
FREE_MODEL = "heygen-voice-1-turbo-free"


class WorkflowError(Exception):
    pass


def note(msg):
    print(f"\n[GamingShorts] {msg}", flush=True)


def check_timing(phrases, number, audio_seconds):
    if len(phrases) != number:
        raise WorkflowError(f"Expected {number} phrase timings, got {len(phrases)}")
    results = []
    prev = -1.0
    for i, item in enumerate(phrases, 1):
        if isinstance(item, dict):
            if "index" in item and int(item["index"]) != i:
                raise WorkflowError(f"Speech phrase index mismatch at {i}")
            start = float(item["first_word_start"])
            end = float(item["last_word_end"])
        else:
            start, end = map(float, item)
        if not (0 <= start < end <= audio_seconds + 0.08) or start < prev:
            raise WorkflowError(f"Invalid or overlapping speech timing for line {i}: {start}–{end}")
        results.append((start, end))
        prev = end
    return results


def voice_schema(path: Path, number: int):
    properties = {
        "audio_url": {"type": "string"},
        "duration_seconds": {"type": "number"},
        "cta_start_seconds": {"type": "number"},
        "voice_id": {"type": "string"},
        "model": {"type": "string"},
        "words": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["word", "start", "end"],
                "properties": {
                    "word": {"type": "string"},
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                },
            },
        },
        "phrases": {
            "type": "array",
            "minItems": number,
            "maxItems": number,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "first_word_start", "last_word_end"],
                "properties": {
                    "index": {"type": "integer"},
                    "first_word_start": {"type": "number"},
                    "last_word_end": {"type": "number"},
                },
            },
        },
    }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }
    json_save_atomic(path, schema)


def generate_voice_with_codex(project: Path, clips: list, allow_retry: bool):
    result_path = project / "voice_result.json"
    marker = project / "voice_generation_attempted.json"
    if result_path.is_file():
        return
    if marker.exists() and not allow_retry:
        raise WorkflowError(
            "A HeyGen attempt was already started but no verified result was saved. "
            "The outcome could be uncertain, so automatic retries are blocked. "
            "Check voice_codex.log; only rerun with --retry-voice if you authorize another FREE attempt."
        )
    if not shutil.which("codex"):
        raise WorkflowError("Codex CLI not found in Ubuntu PATH")
    schema = project / "voice_output_schema.json"
    voice_schema(schema, len(clips))
    # The narration is passed as text to Codex; no need to spend image tokens again.
    lines = [c["narration"].strip() for c in clips]
    for i, s in enumerate(lines, 1):
        if not s:
            raise WorkflowError(f"Missing narration for line {i}")
    spoken = " ".join(lines)
    prompt = f"""You are the AUDIO stage of a GamingShorts workflow, not the editor.

The seven (or N) approved narration lines, in their exact order, are:
{json.dumps(lines, ensure_ascii=False)}

Synthesize ONE continuous recording of EXACTLY this text, in this order:
{json.dumps(spoken, ensure_ascii=False)}

Use the authenticated HeyGen MCP tool `create_speech` EXACTLY ONE TIME.
Voice ID: {VOICE_ID} (Garret — Bold & Persuasive, previously verified ACTIVE instant voice).
Model MUST be `{FREE_MODEL}`. Language `en`, expressivenessBoost 1.0,
withTimestamps true. This is VOICE/AUDIO ONLY, not video.

CRITICAL: The user authorizes ONLY the FREE speech model, with no charges,
no paid model, no purchase, no upgrade, no fallback and NO automatic retry.
If the free model cannot generate, DO NOT generate anything else. Report failure.
Do not use HeyGen's paid REST API. Do not modify any local project files.
Do not execute scripts, commands or other unrelated tools.

When the one speech call succeeds, use the ACTUAL returned word timestamps to
compute the first spoken word start and last spoken word end of EACH original
narration line. Return these as `phrases` with 1-based `index` in the same order.
Also return cta_start_seconds: the actual timestamp of the word Subscribe in the FINAL sentence, or -1 if unavailable. Never guess this timestamp.
Return ALL actual source word timestamps in `words`, preserving the returned word,
start and end values as seconds in the continuous audio. Do not interpolate or
invent timings. If actual word timestamps are absent, return an empty words array.
No evenly spaced guesses, no invented times. Return the REAL downloadable WAV
URL, reported duration, exact voice_id, and exact model. Return ONLY valid JSON
conforming to the provided schema. If the audio exists but timing information
cannot be mapped reliably, still return real URL and duration, with zero times
for all phrases; the local server will stop safely and request correction.
"""
    if marker.exists() and allow_retry:
        marker.rename(project / f"voice_generation_retry_{int(time.time())}.json")
    json_save_atomic(
        marker,
        {
            "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "voice_id": VOICE_ID,
            "model": FREE_MODEL,
            "status": "attempted_outcome_unverified_until_result_saved",
        },
    )
    # Put prompt FIRST to avoid the Codex positional parsing bug encountered earlier.
    cmd = [
        "codex",
        "exec",
        prompt,
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--output-schema",
        str(schema),
        "-o",
        str(result_path),
    ]
    note("Calling Codex → HeyGen MCP: one FREE speech generation only")
    log = project / "voice_codex.log"
    with log.open("a", encoding="utf-8") as fout:
        p = subprocess.run(
            cmd,
            cwd=project,
            stdout=fout,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=gs.config()["codex_timeout_seconds"],
        )
    if p.returncode:
        raise WorkflowError(
            f"Voice step failed (Codex exit {p.returncode}). See {log}. "
            "Automatic retries are disabled."
        )
    if not result_path.is_file():
        raise WorkflowError(
            f"Codex returned without producing {result_path}; automatic retries are disabled"
        )
    note("HeyGen MCP returned a structured audio result")


def save_word_timestamps(project, clips, result, audio):
    """Retain returned timestamps for karaoke without another model or speech call."""
    if not result.get("words"):
        return False  # Older saved results may use the optional local aligner.
    from captions import tokens, validate_words

    if result.get("voice_id") != VOICE_ID or result.get("model") != FREE_MODEL:
        raise WorkflowError("Unapproved word-timestamp voice/model")
    measured = gs.duration(audio)
    if abs(float(result["duration_seconds"]) - measured) > 0.10:
        raise WorkflowError("Word timestamp result and saved audio durations differ")
    script = [clip["narration"].strip() for clip in clips]
    words = result["words"]
    validate_words(words, " ".join(script), measured)
    spans = check_timing(result["phrases"], len(clips), measured)
    index = 0
    for line, (first, last) in zip(script, spans):
        count = len(tokens(line))
        selected = words[index : index + count]
        if len(selected) != count or any(len(tokens(word["word"])) != 1 for word in selected):
            raise WorkflowError("Expected one returned timestamp per narration word")
        if (
            abs(float(selected[0]["start"]) - first) > 0.08
            or abs(float(selected[-1]["end"]) - last) > 0.08
        ):
            raise WorkflowError("Word timings disagree with the saved phrase boundaries")
        index += count
    payload = {
        "voice_id": result["voice_id"],
        "model": result["model"],
        "script": script,
        "duration_seconds": result["duration_seconds"],
        "words": words,
        "audio_sha256": digest(audio),
    }
    path = Path(project) / "heygen_word_timestamps.json"
    if path.exists():
        existing = read(path)
        if any(
            existing.get(name) != value for name, value in payload.items() if name != "audio_sha256"
        ):
            raise WorkflowError("Existing word timing result conflicts; preserving it for review")
        if existing.get("audio_sha256", payload["audio_sha256"]) != payload["audio_sha256"]:
            raise WorkflowError("Word timestamp audio checksum mismatch")
    else:
        json_save_atomic(path, payload)
    return True


def download_voice(project: Path, result: dict) -> Path:
    url = result.get("audio_url", "")
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(
        host == d or host.endswith("." + d) for d in ("heygen.ai", "heygen.com")
    ):
        raise WorkflowError("Unexpected HeyGen download domain. Stopped without opening the URL.")
    if result.get("model") != FREE_MODEL:
        raise WorkflowError("Returned voice model was not the explicitly permitted FREE model")
    if result.get("voice_id") != VOICE_ID:
        raise WorkflowError("Voice identity differs from Garret; stopped")
    audio = project / "Audio" / "heygen_full.wav"
    audio.parent.mkdir(exist_ok=True)
    if not audio.is_file():
        tmp = audio.with_suffix(".downloading")
        try:
            gs.download(url, tmp)
            probe = gs.duration(tmp)
            if not (0.2 < probe < 300):
                raise WorkflowError(f"Implausible speech duration {probe}")
            tmp.replace(audio)
        finally:
            if tmp.exists():
                tmp.unlink()
    return audio


def split_speech(project: Path, clips: list, spans: list, audio: Path):
    from audio_pipeline import read_audio, safe_boundaries, quiet_edge_fade, export_segment, POLICY

    audio_seconds = gs.duration(audio)
    timings = check_timing(spans, len(clips), audio_seconds)
    samples = read_audio(audio)
    cuts, boundary_checks = safe_boundaries(samples, timings)
    voices = project / "Voices"
    voices.mkdir(exist_ok=True)
    for i, clip in enumerate(clips):
        dest = voices / f"line_{i + 1:02d}.wav"
        length = cuts[i + 1] - cuts[i]
        scene_seconds = float(clip["duration"])
        if length > scene_seconds - 0.20:
            raise WorkflowError(
                f"Line {i + 1}: narration segment {length:.2f}s won't fit "
                f"its {scene_seconds:.2f}s scene. Edit the blueprint before rendering."
            )
        if not dest.is_file():
            segment = samples[round(cuts[i] * 48000) : round(cuts[i + 1] * 48000)]
            export_segment(quiet_edge_fade(segment), dest)
        measured = gs.duration(dest)
        if measured > scene_seconds - 0.15:
            raise WorkflowError(f"Segment {i + 1} audio is too long after export")
        print(f"  Voice {i + 1}/{len(clips)}: {measured:.2f}s in {scene_seconds:.2f}s scene")
    json_save_atomic(
        project / "voice_timing.json",
        {
            "audio": str(audio),
            "audio_duration_seconds": audio_seconds,
            "source_word_spans": timings,
            "segment_boundaries": cuts,
            "boundary_policy": POLICY,
            "boundary_checks": boundary_checks,
        },
    )
