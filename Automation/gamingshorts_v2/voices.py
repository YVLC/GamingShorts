from pathlib import Path
import shutil
from common import config, key, read, save, digest, state
import gaming_shorts as gs
import voice_bridge as bridge


def request(clips):
    return {
        "lines": [c["narration"].strip() for c in clips],
        "voice_id": config()["voice_id"],
        "model": config()["voice_model"],
        "expressivenessBoost": 1.0,
        "language": "en",
    }


def ensure(project, clips, retry=False, adopt=False, fresh=False):
    p = Path(project)
    req = request(clips)
    identity = key(req)
    folder = p / "VoiceVersions" / identity
    if (p / "active_voice.json").is_file():
        active = read(p / "active_voice.json")
        candidate = (p / active.get("folder", "")).resolve()
        if (
            active.get("request_key") == identity
            and candidate.is_relative_to((p / "VoiceVersions").resolve())
            and (candidate / "provenance.json").is_file()
        ):
            folder = candidate
    folder.mkdir(parents=True, exist_ok=True)
    proof = folder / "provenance.json"
    if proof.exists():
        prov = read(proof)
        if prov["request_key"] != identity:
            raise RuntimeError("Invalid voice request identity")
        expected = {f"line_{i:02d}.wav" for i in range(1, len(clips) + 1)}
        if set(prov["files"]) != expected:
            raise RuntimeError("Incomplete voice provenance")
        for name, sha in prov["files"].items():
            v = folder / "Voices" / name
            if not v.exists() or digest(v) != sha:
                raise RuntimeError(
                    "Verified voice changed or is missing. Restore it or archive this voice version before retrying."
                )
    else:
        legacy = [p / "Voices" / f"line_{i:02d}.wav" for i in range(1, len(clips) + 1)]
        legacy_present = any(v.exists() for v in legacy) or any(
            (p / f).exists()
            for f in (
                "Audio/heygen_full.wav",
                "voice_result.json",
                "voice_generation_attempted.json",
            )
        )
        if legacy_present and not (p / "active_voice.json").exists() and not fresh:
            if (p / "legacy_plan_snapshot.json").exists() and [
                c["narration"] for c in read(p / "legacy_plan_snapshot.json")["clips"]
            ] != [c["narration"] for c in clips]:
                raise RuntimeError(
                    "Legacy text changed. Use --new-voice to request matching free speech; old audio will be kept."
                )
            if not adopt:
                raise RuntimeError(
                    "Legacy narration has no text provenance. Listen to every line and compare edit_plan.json. If it matches, run with --adopt-legacy-voice. No speech was regenerated."
                )
            if all(v.exists() for v in legacy):
                (folder / "Voices").mkdir(exist_ok=True)
                for v in legacy:
                    shutil.copyfile(v, folder / "Voices" / v.name)
            elif (p / "Audio/heygen_full.wav").exists() and (p / "voice_result.json").exists():
                result = read(p / "voice_result.json")
                (folder / "Audio").mkdir(exist_ok=True)
                audio = folder / "Audio/heygen_full.wav"
                shutil.copyfile(p / "Audio/heygen_full.wav", audio)
                bridge.split_speech(folder, clips, result["phrases"], audio)
            else:
                raise RuntimeError(
                    "Legacy audio is incomplete or its generation outcome is uncertain. Recover the saved result/audio, or explicitly use --new-voice for a new FREE generation."
                )
            origin = "user_attested_legacy_audio"
        else:
            bridge.VOICE_ID = req["voice_id"]
            bridge.FREE_MODEL = req["model"]
            audio = folder / "Audio" / "heygen_full.wav"
            result = folder / "voice_result.json"
            # Recover a saved result without another synthesis call.
            if not result.exists() and not audio.exists():
                bridge.generate_voice_with_codex(folder, clips, retry)
            if not result.exists():
                raise RuntimeError(
                    "Audio exists without its phrase timing result; recover voice_result.json. No automatic retry."
                )
            r = read(result)
            if r.get("voice_id") != req["voice_id"] or r.get("model") != req["model"]:
                raise RuntimeError("Speech result used an unapproved voice/model")
            if not audio.exists():
                audio = bridge.download_voice(folder, r)
            # A partial split is re-created from the saved full audio, never re-synthesized.
            for f in (folder / "Voices").glob("line_*.wav"):
                f.unlink()
            bridge.split_speech(folder, clips, r["phrases"], audio)
            bridge.save_word_timestamps(folder, clips, r, audio)
            origin = "free_mcp_generation"
        files = {}
        for i in range(1, len(clips) + 1):
            v = folder / "Voices" / f"line_{i:02d}.wav"
            if gs.duration(v) <= 0.05:
                raise RuntimeError("Empty voice file")
            files[v.name] = digest(v)
        provenance = {"request_key": identity, "request": req, "files": files, "origin": origin}
        if (
            origin == "free_mcp_generation"
            and isinstance(r.get("cta_start_seconds"), (int, float))
            and r["cta_start_seconds"] >= 0
        ):
            timing = read(folder / "voice_timing.json")
            cta = float(r["cta_start_seconds"])
            lo, hi = timing["source_word_spans"][-1]
            if not lo <= cta < hi:
                raise RuntimeError("CTA timestamp outside the final speech phrase")
            provenance["cta_offset_seconds"] = cta - timing["segment_boundaries"][-2]
        save(proof, provenance)
    for i, c in enumerate(clips, 1):
        if gs.duration(folder / "Voices" / f"line_{i:02d}.wav") > float(c["duration"]) - 0.15:
            raise RuntimeError(
                f"Voice line {i} does not fit. Extend its scene or shorten narration. Existing audio preserved."
            )
    save(p / "active_voice.json", {"folder": str(folder.relative_to(p)), "request_key": identity})
    state(p, "voiced", request_key=identity)
    return folder


def repair_boundaries(project, clips):
    """Create a new audio-byte version from the saved master; never request TTS."""
    import audio_pipeline

    p = Path(project)
    active = read(p / "active_voice.json")
    previous = p / active["folder"]
    proof = read(previous / "provenance.json")
    req = request(clips)
    if proof["request_key"] != key(req):
        raise RuntimeError("Saved narration text/settings do not match this plan")
    for name, sha in proof["files"].items():
        if digest(previous / "Voices" / name) != sha:
            raise RuntimeError("Existing narration checksum mismatch")
    master = previous / "Audio/heygen_full.wav"
    if not master.is_file():
        raise RuntimeError(
            "Continuous original narration is missing; no automatic speech call will be made"
        )
    raw_sha = digest(master)
    revision = key(
        {"request": key(req), "master": raw_sha, "policy": digest(Path(audio_pipeline.__file__))}
    )[:16]
    folder = p / "VoiceVersions" / (key(req) + "_boundary_" + revision)
    if not (folder / "provenance.json").exists():
        (folder / "Audio").mkdir(parents=True, exist_ok=True)
        target = folder / "Audio/heygen_full.wav"
        if not target.exists():
            shutil.copy2(master, target)
        if digest(target) != raw_sha:
            raise RuntimeError("Saved repair master differs; preserve it for investigation")
        timing = read(previous / "voice_timing.json")
        bridge.split_speech(folder, clips, timing["source_word_spans"], target)
        for name in ("heygen_word_timestamps.json", "voice_result.json"):
            if (previous / name).exists() and not (folder / name).exists():
                shutil.copy2(previous / name, folder / name)
        updated = dict(
            proof,
            files={
                f"line_{i:02d}.wav": digest(folder / "Voices" / f"line_{i:02d}.wav")
                for i in range(1, len(clips) + 1)
            },
            origin="existing_master_boundary_revision",
            derived_from=str(previous.relative_to(p)),
            master_sha256=raw_sha,
            boundary_policy=audio_pipeline.POLICY,
        )
        if "cta_offset_seconds" in proof:
            absolute = timing["segment_boundaries"][-2] + proof["cta_offset_seconds"]
            updated["cta_offset_seconds"] = (
                absolute - read(folder / "voice_timing.json")["segment_boundaries"][-2]
            )
        save(folder / "provenance.json", updated)
    save(p / "active_voice.json", {"folder": str(folder.relative_to(p)), "request_key": key(req)})
    return folder
