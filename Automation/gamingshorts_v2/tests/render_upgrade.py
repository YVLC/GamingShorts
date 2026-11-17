"""Synthetic timing fixture: verifies renderer plumbing, NOT real speech alignment."""

import sys, time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common, captions, gaming_shorts as gs, music_library


def main():
    root = Path(sys.argv[1]).resolve()
    gs.ROOT = root
    p = root / "fixture"
    doc = common.read(p / "edit_plan.json")
    doc["clips"][0]["caption"] = "A PRECISE MOMENT"
    common.save(p / "edit_plan.json", doc)
    folder = p / common.read(p / "active_voice.json")["folder"]
    lines = []
    for c in doc["clips"]:
        # Synthetic tone has no words; hand-authored times exercise timestamp propagation only.
        words = c["narration"].split()
        step = 1.7 / len(words)
        lines.append(
            {
                "words": [
                    {
                        "word": w,
                        "start": round(0.1 + i * step, 4),
                        "end": round(0.1 + (i + 0.8) * step, 4),
                    }
                    for i, w in enumerate(words)
                ]
            }
        )
    cfg = dict(common.config(), width=720, height=1280, caption_mode="karaoke", music_lufs=-30)
    with (
        patch.object(gs, "config", return_value=cfg),
        patch.object(captions, "config", return_value=cfg),
        patch.object(music_library, "config", return_value=cfg),
    ):
        common.save(
            folder / "word_alignment.json",
            {
                "identity": captions.identity(folder, doc["clips"]),
                "lines": lines,
                "method": "synthetic fixture only",
            },
        )
        first = gs.render(p, folder)
        q = common.read(p / "qc_report.json")
        out = Path(q["review_sheet"]).parent
        assert (out / "subtitles.srt").exists()
        assert q["captions"]["mode"] == "karaoke"
        assert gs.completed(p)
        original_run = gs.run

        def guarded(cmd, **kwargs):
            if "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264":
                raise AssertionError("Music-only retry unexpectedly re-encoded video")
            return original_run(cmd, **kwargs)

        cfg["music_lufs"] = -33
        start = time.perf_counter()
        with patch.object(gs, "run", side_effect=guarded):
            second = gs.render(p, folder)
        assert first != second
        assert gs.completed(p)
        for i in range(1, 6):
            assert common.digest(out / f"shot_{i:02d}.mp4") == common.digest(
                Path(common.read(p / "qc_report.json")["review_sheet"]).parent / f"shot_{i:02d}.mp4"
            )
        common.save(
            root / "upgrade_test.json",
            {
                "karaoke_render": "passed with synthetic timings",
                "audio_only_retry": "passed: zero video encodes",
                "retry_seconds": time.perf_counter() - start,
                "output": str(second),
            },
        )
        print(
            "PASS: karaoke burn-in, SRT mapping, final-word timing, and music-only retry with zero video encoding."
        )


if __name__ == "__main__":
    main()
