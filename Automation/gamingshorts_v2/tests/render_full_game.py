"""Real FFmpeg index/validation fixture. Synthetic gameplay; no AI or speech calls."""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import digest, save
import gaming_shorts as gs
from game_store import GameStore
from job_store import JobStore
import game_index
from source_validation import decode_source, inspect_source, SourceValidationError


def main():
    destination = Path(sys.argv[1]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="full-game-media-") as directory:
        root = Path(directory)
        with patch.object(gs, "ROOT", root):
            source = root / "GameSources/cairn/synthetic.mp4"
            source.parent.mkdir(parents=True)
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=1280x720:rate=30",
                    "-t",
                    "12",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-threads",
                    "2",
                    str(source),
                ],
                check=True,
            )
            os.utime(source, (time.time() - 120, time.time() - 120))
            before = digest(source)
            queue = JobStore(root)
            proof = queue.admit_source(source)
            store = GameStore()
            recording = store.register("cairn", "Synthetic fixture", proof)
            store.select("cairn")
            game_index.verify_integrity(recording)
            with queue.connect() as db:
                assert db.execute("SELECT count(*) FROM decode_checkpoints").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM decoded_sources").fetchone()[0] == 1
            with patch.object(
                game_index, "decode_source", side_effect=AssertionError("repeated decode")
            ):
                game_index.verify_integrity(recording)
            folder = root / "FootageIndex/chunk"
            artifacts = game_index.make_artifacts(recording, folder, 7, 12)
            assert artifacts["start"] == 7 and artifacts["end"] == 12
            proxy = folder / "analysis.mp4"
            metadata = gs.probe(proxy)
            video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
            assert video["width"] == 640 and video["avg_frame_rate"] == "2/1"
            assert abs(gs.duration(proxy) - 5) < 0.1
            assert list(folder.glob("sheet_*.jpg"))
            with patch.object(
                game_index, "checked_decode", side_effect=AssertionError("cache not reused")
            ):
                assert game_index.make_artifacts(recording, folder, 7, 12) == artifacts
            rows = game_index.validate_scenes(
                {
                    "scenes": [
                        {
                            "start": 8,
                            "end": 11,
                            "description": "Moving geometric fixture",
                            "category": "action",
                            "confidence": 0.9,
                            "spoiler": "none",
                            "evidence": "Colored shapes change position",
                            "tags": ["fixture"],
                            "interest": 0.8,
                        }
                    ]
                },
                recording,
                0,
                7,
                12,
                folder,
                "fixture",
            )
            assert rows[0][4:6] == (8, 11)
            assert len(__import__("json").loads(rows[0][12])) == 3
            receipt = decode_source(source, proof["probe"], start=7, seconds=5, timeout=600)
            assert receipt["frames"] == 150
            assert abs(receipt["duration_seconds"] - 5) < 0.1
            try:
                decode_source(source, proof["probe"], start=10, seconds=5, timeout=600)
            except SourceValidationError:
                pass
            else:
                raise AssertionError("Truncated checkpoint range was accepted")
            assert digest(source) == before
            codec_results = []
            encoders = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=True
            ).stdout
            for encoder, codec, options in (
                ("libx265", "hevc", ["-x265-params", "log-level=error:pools=1:frame-threads=1"]),
                ("libaom-av1", "av1", ["-cpu-used", "8"]),
            ):
                if encoder not in encoders:
                    codec_results.append(
                        {"codec": codec, "status": "encoder unavailable; fixture skipped"}
                    )
                    continue
                fixture = root / (codec + ".mp4")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-nostdin",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=128x72:rate=12",
                        "-t",
                        "2",
                        "-c:v",
                        encoder,
                        "-threads",
                        "2",
                        *options,
                        str(fixture),
                    ],
                    check=True,
                    timeout=120,
                )
                _, _, document = inspect_source(fixture, details=True)
                assert document["streams"][0]["codec_name"] == codec
                decoded = decode_source(fixture, document, start=0, seconds=2, timeout=120)
                assert decoded["frames"] == 24
                codec_results.append(
                    {"codec": codec, "status": "strict packet and window decode pass"}
                )
            for image in folder.glob("sheet_*.jpg"):
                shutil.copy2(image, destination / image.name)
            save(destination / "artifacts.json", artifacts)
            save(
                destination / "verification.json",
                {
                    "source_unchanged": True,
                    "late_global_interval": [7, 12],
                    "proxy_resolution": [640, 360],
                    "proxy_fps": 2,
                    "validation_receipt_reused": True,
                    "checkpoint_frames": receipt["frames"],
                    "no_ai_calls": True,
                    "codec_fixtures": codec_results,
                    "note": "Actual FFmpeg fixture; long duration/60 GB behavior is covered by orchestration and 64-bit regression fixtures, not a real 60 GB benchmark.",
                },
            )
            print(
                "PASS: strict checkpoint decode, receipt reuse, late-source proxy, global contact-sheet timestamps, visual hashes, cache reuse, truncated range rejected, original unchanged."
            )


if __name__ == "__main__":
    main()
