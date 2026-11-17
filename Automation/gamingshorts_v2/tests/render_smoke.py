"""Offline end-to-end FFmpeg fixture; no Codex/HeyGen calls. Uses temporary data only."""

import sys, tempfile, json, math, wave, array, contextlib
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common, gaming_shorts as gs, editorial, voices


@patch.object(gs, "config", return_value=dict(common.DEFAULTS))
def main(_config):
    with (
        contextlib.nullcontext(sys.argv[2])
        if len(sys.argv) > 2
        else tempfile.TemporaryDirectory(prefix="gamingshorts-render-test-")
    ) as tmp:
        root = Path(tmp).resolve()
        gs.ROOT = root
        p = root / "fixture"
        p.mkdir(parents=True, exist_ok=True)
        src = root / "source.mp4"
        common.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=640x360:rate=30",
                "-t",
                "26",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-threads",
                "2",
                src,
            ]
        )
        common.save(
            p / "manifest.json",
            {"source": str(src), "source_sha256": common.digest(src), "duration": 26},
        )
        clips = []
        for i in range(1, 6):
            clips.append(
                {
                    "start": (i - 1) * 5,
                    "duration": 5,
                    "caption": "A PRECISE MOMENT" if i < 5 else "THE FINAL PAYOFF",
                    "narration": "A synthetic audio fixture."
                    if i < 5
                    else "The final payoff. Subscribe for more.",
                }
            )
            v = p / "Voices" / f"line_{i:02d}.wav"
            v.parent.mkdir(exist_ok=True)
            samples = [
                int(
                    7000
                    * (0.4 + 0.6 * math.sin(j / 16000 * math.pi * 3) ** 2)
                    * math.sin(2 * math.pi * (180 + i * 40) * j / 16000)
                )
                for j in range(32000)
            ]
            with wave.open(str(v), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(array.array("h", samples).tobytes())
        common.save(p / "edit_plan.json", {"clips": clips})
        folder = voices.ensure(p, clips, adopt=True)
        final = gs.render(p, folder)
        assert gs.completed(p), "Completed output not recognized"
        report = common.read(p / "qc_report.json")
        print("POSITIVE_QC", json.dumps(report), flush=True)
        # A dropped narration track must fail even when the file has music/audio.
        out = Path(report["review_sheet"]).parent
        bad = out / "music_only.mp4"
        common.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                out / "video.mp4",
                "-i",
                out / "music.wav",
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-t",
                "25",
                bad,
            ]
        )
        neg = gs.qc(
            bad,
            out / "speech.wav",
            out / "music.wav",
            [[0.15 + 5 * i, 2.15 + 5 * i] for i in range(4)] + [[22.9, 24.9]],
            25,
            out,
            gs.config(),
        )
        assert neg["status"] == "failed", "Music-only final passed"
        print("NEGATIVE_QC", json.dumps(neg["errors"]), flush=True)
        clips[0]["caption"] = "CHANGED CAPTION"
        common.save(p / "edit_plan.json", {"clips": clips})
        assert not gs.completed(p), "Changed plan incorrectly reused completed render"
        # Exercise dense/survey contact-sheet generation too.
        frames = p / "frames"
        frames.mkdir()
        editorial.sheet(src, 5, 10, frames / "dense.jpg", "dense")
        assert (frames / "dense.jpg").stat().st_size > 1000
        if len(sys.argv) > 1:
            import shutil

            dest = Path(sys.argv[1])
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(out / "review_sheet.jpg", dest / "review_sheet.jpg")
            shutil.copyfile(frames / "dense.jpg", dest / "dense.jpg")
            shutil.copyfile(final, dest / "fixture.mp4")
            common.save(dest / "fixture_qc.json", report)
        print(
            "PASS: actual render, complete decode, mixed-audio QC, missing-narration rejection, cache invalidation, and contact sheets."
        )


if __name__ == "__main__":
    main()
