"""End-to-end synthetic word-timestamp fixture; never calls an AI service."""

from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import captions
import common
import gaming_shorts as gs
import music_library
import voices
from test_regressions import tone


def main():
    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="word-handoff-fixture-") as temporary:
        gs.ROOT = root = Path(temporary)
        project = root / "word_fixture"
        source = root / "source.mp4"
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
                "testsrc2=size=1920x1080:rate=30",
                "-t",
                "26",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-threads",
                "2",
                source,
            ]
        )
        common.save(
            project / "manifest.json",
            {"source": str(source), "source_sha256": common.digest(source), "duration": 26},
        )
        clips = [
            {
                "start": index * 5,
                "duration": 5,
                "caption": "SYNTHETIC TIMING TEST",
                "framing":"tracked_cover",
                "narration": "A synthetic audio fixture."
                if index < 4
                else "The final payoff. Subscribe for more.",
            }
            for index in range(5)
        ]
        import story_policy
        common.save(project / "edit_plan.json", {"clips": clips,'editorial':{
            'policy':story_policy.VERSION,'story_type':'beginner_tip','story_basis':'gameplay_demonstration',
            'viewer_value':'Synthetic fixture for complete narrated beats',
            'hook_promise':'A fixture hook','payoff_evidence':'Synthetic moving test pattern',
            'narration_added_value':'Fixture commentary',
            'claims':[{'claim':'Synthetic fixture','evidence':'Generated test pattern','basis':'footage','reference_id':''}]}})
        folder = project / "VoiceVersions" / common.key(voices.request(clips))
        tone(folder / "Audio/heygen_full.wav", 10)
        import wave
        import array

        audio_file = folder / "Audio/heygen_full.wav"
        with wave.open(str(audio_file), "rb") as reader:
            parameters = reader.getparams()
            samples = array.array("h", reader.readframes(reader.getnframes()))
        for boundary in (2, 4, 6, 8):
            lo, hi = round((boundary - 0.25) * 16000), round((boundary + 0.05) * 16000)
            samples[lo:hi] = array.array("h", [0] * (hi - lo))
        with wave.open(str(audio_file), "wb") as writer:
            writer.setparams(parameters)
            writer.writeframes(samples.tobytes())
        words, phrases = [], []
        for index, clip in enumerate(clips):
            tokens = clip["narration"].split()
            step = 1.6 / len(tokens)
            row = [
                {
                    "word": token,
                    "start": index * 2 + 0.1 + i * step,
                    "end": index * 2 + 0.1 + (i + 0.8) * step,
                }
                for i, token in enumerate(tokens)
            ]
            words.extend(row)
            phrases.append(
                {
                    "index": index + 1,
                    "first_word_start": row[0]["start"],
                    "last_word_end": row[-1]["end"],
                }
            )
        result = {
            "voice_id": common.config()["voice_id"],
            "model": "heygen-voice-1-turbo-free",
            "duration_seconds": 10,
            "phrases": phrases,
            "words": words,
            "cta_start_seconds": words[-3]["start"],
        }
        common.save(folder / "voice_result.json", result)
        cfg = dict(common.DEFAULTS, width=720, height=1280, caption_mode="karaoke")
        with (
            patch.object(story_policy,'require_review'),
            patch.object(gs, "config", return_value=cfg),
            patch.object(captions, "config", return_value=cfg),
            patch.object(music_library, "config", return_value=cfg),
        ):
            verified = voices.ensure(project, clips)
            aligned = captions.align(project)
            assert "actual source word timestamps" in aligned["method"]
            final = gs.render(project, verified)
            assert gs.completed(project)
            report = common.read(project / "qc_report.json")
            assert report["status"] == "technical_pass"
            assert report["captions"]["mode"] == "karaoke"
            shutil.copyfile(final, destination / "karaoke-fixture.mp4")
            shutil.copyfile(report["review_sheet"], destination / "karaoke-review.jpg")
            common.save(destination / "karaoke-qc.json", report)
            common.save(destination / "synthetic-word-alignment.json", aligned)
            print(
                "PASS: saved result -> split -> verified voice -> real-timestamp path -> karaoke render -> final QC"
            )
            print(
                "Timestamps are hand-authored fixture data; no claim of real speech synchronization."
            )


if __name__ == "__main__":
    main()
