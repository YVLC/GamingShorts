#!/usr/bin/env python3
"""GamingShorts V2: one-command workflow with retained versions and explicit review."""

from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from common import HERE, VERSION, config, digest, key, locked, now, read, save, state
import gaming_shorts as gs
import editorial, voices


def slug(name):
    return re.sub("[^a-z0-9]+", "_", Path(name).stem.lower()).strip("_")[:42] or "recording"


def project_for(src, variant="main"):
    # Path digest avoids collisions between identically named recordings. Source checksum is separately enforced.
    return (
        gs.ROOT
        / "Projects"
        / "V2"
        / (slug(src.name) + "_" + key(str(src.resolve()))[:8] + "_" + slug(variant))
    )


def prepare(src, variant="main", *, verified_source=None, full_game_context=None):
    from quality_checks import production_source

    production_source(src)
    src = Path(src).resolve()
    if not src.is_file():
        raise ValueError(f"Source missing: {src}")
    p = project_for(src, variant)
    if src.is_relative_to((gs.ROOT / "GameSources").resolve()) and not full_game_context:
        existing = read(p / "manifest.json") if (p / "manifest.json").exists() else {}
        if not existing.get("full_game"):
            raise ValueError("GameSources recordings require the explicit --v3 batch workflow")
    p.mkdir(parents=True, exist_ok=True)
    before = src.stat()
    if verified_source:
        from source_validation import fingerprint

        if (
            str(src) != verified_source["source"]
            or json.dumps(fingerprint(before), separators=(",", ":"))
            != verified_source["fingerprint"]
        ):
            raise ValueError("Source changed after queue integrity validation")
    m = p / "manifest.json"
    # Reusing an unchanged source for a new task must not re-hash the whole 90-minute recording.
    # The renderer still verifies its full SHA256 before producing a final video.
    if m.exists():
        known = read(m)
        if verified_source and known.get("source_sha256") != verified_source["sha256"]:
            raise ValueError("Source checksum differs from existing project; project preserved")
        if (
            known.get("source_size_bytes") == before.st_size
            and known.get("source_modified_ns") == before.st_mtime_ns
        ):
            print(
                "Reusing unchanged recording metadata; full hash deferred to rendering.", flush=True
            )
            return p
    sha = verified_source["sha256"] if verified_source else None
    if not m.exists() and sha is None:
        # All variants can trust a previously verified manifest for the SAME path and file metadata.
        # FFmpeg final rendering still performs a full content digest.
        for existing in (gs.ROOT / "Projects" / "V2").glob("*/manifest.json"):
            try:
                prior = read(existing)
                if (
                    Path(prior["source"]).resolve() == src
                    and prior.get("source_size_bytes") == before.st_size
                    and prior.get("source_modified_ns") == before.st_mtime_ns
                    and prior.get("source_sha256")
                ):
                    sha = prior["source_sha256"]
                    break
            except (ValueError, OSError, KeyError):
                continue
    if sha:
        print(
            "Reusing verified recording SHA256 from existing project; no full-file rescan.",
            flush=True,
        )
    else:
        print("Hashing new/changed source recording...", flush=True)
        sha = digest(src)
    after = src.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source is still changing. Wait until copying/recording finishes.")
    if m.exists():
        if read(m)["source_sha256"] != sha:
            raise ValueError(
                "Source changed in place. Rename the new recording or use a new --variant."
            )
        saved = read(m)
        saved.update(source_size_bytes=after.st_size, source_modified_ns=after.st_mtime_ns)
        save(m, saved)
        return p
    secs = gs.duration(src)
    if secs < config()["min_seconds"]:
        raise ValueError("Recording too short for the configured Short duration")
    save(
        m,
        {
            "source": str(src),
            "source_sha256": sha,
            "source_size_bytes": src.stat().st_size,
            "source_modified_ns": src.stat().st_mtime_ns,
            "duration": secs,
            "name": src.name,
            "created_utc": now(),
            **({"full_game": full_game_context} if full_game_context else {}),
        },
    )
    state(p, "prepared")
    return p


def archive_plan(p):
    if (p / "edit_plan.json").exists():
        editorial.remember(p, "superseded")
        dest = p / "PlanHistory" / key(read(p / "edit_plan.json"))
        dest.mkdir(parents=True, exist_ok=True)
        for name in ("edit_plan.json", "story_candidates.json", "qc_report.json", "approval.json"):
            if (p / name).exists():
                shutil.copy2(p / name, dest / name)
        (p / "edit_plan.json").unlink()
        for name in ("approval.json", "qc_report.json"):
            if (p / name).exists():
                (p / name).unlink()


def migrate(old):
    old = Path(old).resolve()
    m = read(old / "manifest.json")
    src = Path(m["source"]).resolve()
    if not src.is_file():
        raise RuntimeError("Original recording missing; cannot migrate for rendering")
    dest = gs.ROOT / "Projects" / "V2" / (old.name + "_import_" + key(str(old))[:8])
    if dest.exists():
        raise RuntimeError(f"Migration destination already exists. Resume it with --project {dest}")
    dest.mkdir(parents=True)
    for name in (
        "edit_plan.json",
        "heygen_result.txt",
        "voice_result.json",
        "voice_timing.json",
        "voice_generation_attempted.json",
    ):
        if (old / name).exists():
            shutil.copy2(old / name, dest / name)
    for name in ("Voices", "Audio"):
        if (old / name).is_dir():
            shutil.copytree(old / name, dest / name)
    m.update(source=str(src), source_sha256=digest(src), imported_from=str(old))
    save(dest / "manifest.json", m)
    if (dest / "edit_plan.json").exists():
        save(dest / "legacy_plan_snapshot.json", read(dest / "edit_plan.json"))
        editorial.remember(
            dest, "imported", "Legacy audio requires explicit text attestation before adoption."
        )
    state(dest, "imported")
    print("Migrated copy:", dest)
    print(
        "Original project unchanged. Resume with --project and, only after listening/comparing, --adopt-legacy-voice."
    )
    return dest


def import_history():
    n = 0
    for p in sorted((gs.ROOT / "Projects" / "Automated").glob("*/edit_plan.json")):
        m = p.parent / "manifest.json"
        if not m.exists():
            continue
        try:
            editorial.remember(
                p.parent, "legacy", "Imported editorial history; output approval unknown."
            )
            n += 1
        except (ValueError, KeyError) as e:
            print("Skipped history:", p, e)
    print("Legacy histories indexed:", n)


def doctor():
    failures = []
    import importlib.util

    if importlib.util.find_spec("numpy") is None:
        failures.append("NumPy missing; install requirements-quality.txt before speech/rendering")
    print("GamingShorts", VERSION, "| Python", sys.version.split()[0], "| root", gs.ROOT)
    if os.name != "posix":
        failures.append("Use Ubuntu/WSL, not Windows Python")
    for exe in ("ffmpeg", "ffprobe", "codex"):
        found = shutil.which(exe)
        print(exe, found or "MISSING")
        if not found:
            failures.append(exe + " missing")
    if not Path(config()["font"]).is_file():
        failures.append("Configured font missing")
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
        ffmpeg_filters = r.stdout
        for f in ("drawtext", "loudnorm", "alimiter", "blackdetect", "freezedetect"):
            if f not in r.stdout:
                failures.append("FFmpeg filter missing: " + f)
        limiter = subprocess.run(
            ["ffmpeg", "-hide_banner", "-h", "filter=alimiter"], capture_output=True, text=True
        )
        if "latency" not in limiter.stdout:
            failures.append("FFmpeg alimiter lacks latency compensation")
    if shutil.which("codex"):
        r = subprocess.run(["codex", "exec", "--help"], capture_output=True, text=True, timeout=30)
        for flag in ("--output-schema", "--image", "--ephemeral", "--sandbox"):
            if flag not in r.stdout:
                failures.append("Codex CLI does not advertise " + flag)
        login = subprocess.run(
            ["codex", "login", "status"], capture_output=True, text=True, timeout=30
        )
        print("Codex login:", (login.stdout + login.stderr).strip())
        if login.returncode:
            failures.append("Codex login not ready")
    print("Caption mode:", config().get("caption_mode", "phrase"))
    if config().get("caption_mode") == "karaoke" and shutil.which("ffmpeg"):
        if not re.search(r"\bass\s", ffmpeg_filters):
            failures.append("FFmpeg libass filter missing")
        alignment = Path(config().get("alignment_python", str(HERE / ".align-venv/bin/python")))
        print(
            "Karaoke: real returned HeyGen words first; optional local alignment fallback:",
            "available" if alignment.is_file() else "not installed",
        )
    print(
        "Free HeyGen availability is checked at the actual speech call; doctor does not generate audio."
    )
    if failures:
        raise RuntimeError("; ".join(failures))
    print("Environment checks passed. Run --self-test for offline regression tests.")


def choose(variant):
    from common import configured_source

    selected = configured_source()
    if selected is not None:
        if not selected.is_file():
            raise ValueError(f"Configured active source missing: {selected}")
        return selected
    folder = gs.ROOT / "Sources"
    folder.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        (
            p
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for src in candidates:
        if time.time() - src.stat().st_mtime < 60:
            continue
        p = project_for(src, variant)
        # Existing V1 projects are not implicitly converted or regenerated.
        legacy = gs.ROOT / "Projects" / "Automated" / slug(src.name)
        if legacy.exists() and not p.exists():
            print("Legacy source: use --migrate first:", legacy)
            continue
        if not gs.completed(p):
            return src
    raise RuntimeError(
        "No new or unfinished V2 sources. Add a recording, migrate an old project, or use --source explicitly."
    )


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--v3":
        from full_game import main as full_game_main
        full_game_main(sys.argv[2:])
        return
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--v3", action="store_true", help="Use --v3 --help for full-game selection, indexing and controlled batches (put --v3 first)")
    ap.add_argument("--project", type=Path)
    ap.add_argument("--source", type=Path)
    ap.add_argument("--variant", default="main")
    ap.add_argument("--list-projects", action="store_true")
    ap.add_argument("--doctor", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--migrate", type=Path)
    ap.add_argument("--import-history", action="store_true")
    ap.add_argument("--replan", action="store_true")
    ap.add_argument("--stop-after", choices=["plan", "voice"])
    ap.add_argument("--retry-voice", action="store_true")
    ap.add_argument("--adopt-legacy-voice", action="store_true")
    ap.add_argument(
        "--new-voice",
        action="store_true",
        help="Generate new free audio when legacy text no longer matches; preserves old files",
    )
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--reject", metavar="REASON")
    ap.add_argument("--feedback", metavar="NOTE")
    ap.add_argument("--status", action="store_true")
    ap.add_argument(
        "--align-captions",
        action="store_true",
        help="Align saved audio locally; never generates voice",
    )
    ap.add_argument("--benchmark", type=Path, metavar="VIDEO")
    ap.add_argument("--verify-publication", metavar="YOUTUBE_ID")
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument("--apply-cleanup", action="store_true")
    ap.add_argument(
        "--repair-audio-boundaries",
        action="store_true",
        help="Version new quiet cuts from saved continuous narration; never calls TTS",
    )
    queue_actions = ap.add_mutually_exclusive_group()
    queue_actions.add_argument("--queue", action="store_true", help="List durable automation jobs")
    queue_actions.add_argument(
        "--enqueue", action="store_true", help="Queue --source without generating anything"
    )
    queue_actions.add_argument(
        "--work", action="store_true", help="Process queued jobs once; failures stop for attention"
    )
    queue_actions.add_argument(
        "--watch",
        action="store_true",
        help="Discover stable new recordings and process the durable queue",
    )
    queue_actions.add_argument(
        "--retry-job",
        metavar="ID",
        help="Explicitly resume a stopped job; never authorizes a new speech attempt",
    )
    ap.add_argument("--poll-seconds", type=int, default=30)
    ap.add_argument("--settle-seconds", type=int, default=60)
    a = ap.parse_args()
    a.variant = slug(a.variant)
    if any((a.queue, a.enqueue, a.work, a.watch, a.retry_job)):
        if a.repair_audio_boundaries:
            ap.error("Audio repair requires a direct --project action")
        if any(
            (
                a.project,
                a.doctor,
                a.self_test,
                a.list_projects,
                a.migrate,
                a.import_history,
                a.replan,
                a.retry_voice,
                a.adopt_legacy_voice,
                a.new_voice,
                a.approve,
                a.reject,
                a.feedback,
                a.status,
                a.align_captions,
                a.benchmark,
                a.verify_publication,
                a.cleanup,
                a.apply_cleanup,
            )
        ):
            ap.error("Queue commands cannot be combined with direct project actions")
        if a.source and not a.enqueue:
            ap.error("Only --enqueue accepts --source in queue mode")
        if a.settle_seconds < 60 or not 5 <= a.poll_seconds <= 60:
            ap.error("Use --settle-seconds >= 60 and --poll-seconds between 5 and 60")
        import automation

        automation.handle(a)
        return
    if a.benchmark:
        import benchmark

        with locked(gs.ROOT / "Database" / ".workflow_v2.lock"):
            benchmark.run(a.benchmark, gs.ROOT / "Benchmarks" / time.strftime("%Y%m%d-%H%M%S"))
        return
    if a.self_test:
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(HERE / "tests"), "-v"],
            cwd=HERE,
        )
        raise SystemExit(r.returncode)
    if a.doctor:
        doctor()
        return
    if a.list_projects:
        for kind in ("Automated", "V2"):
            for m in sorted((gs.ROOT / "Projects" / kind).glob("*/manifest.json")):
                print(kind + ": " + str(m.parent))
        return
    if a.repair_audio_boundaries and not a.project:
        ap.error("Audio repair requires --project")
    if a.source and a.project:
        ap.error("Choose --source or --project")
    if a.approve and a.reject:
        ap.error("Choose approval or rejection")
    if (
        any(
            (
                a.approve,
                a.reject,
                a.feedback,
                a.status,
                a.align_captions,
                a.verify_publication,
                a.cleanup,
                a.apply_cleanup,
            )
        )
        and not a.project
    ):
        ap.error("This action requires --project")
    with locked(gs.ROOT / "Database" / ".workflow_v2.lock"):
        if a.migrate:
            migrate(a.migrate)
            return
        if a.import_history:
            import_history()
            return
        p = (
            a.project.expanduser().resolve()
            if a.project
            else prepare(a.source or choose(a.variant), a.variant)
        )
        if not (p / "manifest.json").exists():
            raise ValueError("Missing manifest.json")
        if a.repair_audio_boundaries:
            doc = gs.validate(p)
            folder = voices.repair_boundaries(p, doc["clips"])
            print("Repaired narration version from existing master:", folder)
            return
        if a.align_captions:
            import captions

            captions.align(p)
            print(
                "Saved word alignment. To render highlights, set caption_mode to karaoke in config.json."
            )
            return
        if a.verify_publication:
            import publication

            publication.verify(p, a.verify_publication)
            return
        if a.cleanup or a.apply_cleanup:
            import publication

            publication.cleanup(p, apply=a.apply_cleanup)
            return
        if a.status:
            print(
                json.dumps(
                    read(p / "state.json") if (p / "state.json").exists() else {"stage": "unknown"},
                    indent=2,
                )
            )
            print("Current output validates:", gs.completed(p))
            return
        if a.approve:
            if read(p / "manifest.json").get("full_game"):
                from game_plan import guard
                guard(p, gs.validate(p), require_active=False)
            if not gs.completed(p):
                raise RuntimeError("Cannot approve: output missing, changed, stale, or QC failed")
            q = read(p / "qc_report.json")
            approval_metadata = {
                "output_sha256": q["output_sha256"],
                "input_key": q["input_key"],
                "approved_utc": now(),
            }
            save(
                p / "approval.json",
                approval_metadata,
            )
            editorial.remember(p, "approved")
            state(p, "approved", output=q["output"])
            print("Approved. No automatic publication.")
            return
        if a.reject:
            editorial.remember(p, "rejected", a.reject)
            if (p / "approval.json").exists():
                (p / "approval.json").unlink()
            state(p, "rejected", reason=a.reject)
            print("Feedback saved. Use --replan to create a different story.")
            return
        if a.feedback:
            editorial.remember(p, "feedback", a.feedback)
            print("Feedback saved.")
            return
        try:
            from quality_checks import production_source

            metadata = read(p / "manifest.json")
            if not metadata.get("source_bundle"):
                production_source(metadata["source"])
            if a.stop_after != "plan":
                import importlib.util

                if importlib.util.find_spec("numpy") is None:
                    raise RuntimeError(
                        "NumPy required for waveform/cadence QC; no speech call was made"
                    )
            if a.replan:
                archive_plan(p)
            if not (p / "edit_plan.json").exists():
                editorial.plan(p)
            doc = gs.validate(p)
            if doc.get('editorial',{}).get('policy') in ('gaming-stories-v1','gaming-stories-v2') and not metadata.get('full_game'):
                from story_policy import require_review as require_story_review
                require_story_review(p,doc)
            if doc.get('editorial',{}).get('policy')=='dialogue-editorial-v1':
                from dialogue_editorial import run_project
                if a.stop_after=='plan':return
                if a.stop_after=='voice':raise ValueError('Use a complete dialogue-mode run; gameplay-first has no voice stage')
                final=run_project(p)
                editorial.remember(p,'validated')
                print('READY FOR REVIEW:',final)
                return
            editorial.check_ranges(p, doc)
            if doc.get("editorial", {}).get("beats"):
                editorial.check_blueprint(p, doc)
            if a.stop_after == "plan":
                print("Plan ready:", p / "edit_plan.json")
                return
            if gs.completed(p):
                print("Already validated output:", Path(read(p / "qc_report.json")["output"]))
                return
            if metadata.get("full_game"):
                from game_plan import preflight
                preflight(p, doc)
            else:
                from visual_preflight import require_review as require_visual_review
                require_visual_review(p,doc)
            # Story/footage originality is checked before music selection and TTS.
            from creative_history import require_review
            require_review(p, doc, invoke=True)
            import music_library
            music_library.select(p)
            vf = voices.ensure(
                p, doc["clips"], retry=a.retry_voice, adopt=a.adopt_legacy_voice, fresh=a.new_voice
            )
            if a.stop_after == "voice":
                print("Verified voice ready:", vf)
                return
            if config().get("caption_mode") == "karaoke":
                import captions

                captions.align(p)
            if metadata.get("full_game"):
                from game_plan import render as full_game_render
                full_game_render(p, vf)
            else:
                gs.render(p, vf)
            final = Path(read(p / "qc_report.json")["output"])
            from upload_metadata import write_metadata
            write_metadata(p)
            editorial.remember(p, "validated")
            print("READY FOR REVIEW:", final)
            print('Watch/listen, then --project "' + str(p) + '" --approve or --reject "reason".')
        except Exception as e:
            state(p, "failed", error=str(e))
            raise


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as e:
        print("STOPPED:", e, file=sys.stderr)
        sys.exit(1)
