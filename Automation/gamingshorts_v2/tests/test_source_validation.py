"""Real FFprobe admission and watcher failure-reporting regression coverage."""

import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import automation
import gaming_shorts as gs
from job_store import JobStore
from source_validation import SourceValidationError, inspect_source


class SourceValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=s=32x32:r=5:d=1",
                    "-c:v",
                    "libx264",
                    str(video),
                ],
                check=True,
            )
            cls.video_bytes = video.read_bytes()
            audio = Path(tmp) / "audio.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=duration=1",
                    "-c:a",
                    "aac",
                    str(audio),
                ],
                check=True,
            )
            cls.audio_bytes = audio.read_bytes()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "Sources/video.mp4"
        self.source.parent.mkdir()
        self.source.write_bytes(self.video_bytes)
        os.utime(self.source, (1, 1))
        self.old_root = gs.ROOT
        gs.ROOT = self.root
        self.store = JobStore(self.root)

    def tearDown(self):
        gs.ROOT = self.old_root
        self.tmp.cleanup()

    def test_real_video_admitted_by_store(self):
        self.assertEqual(self.store.enqueue(self.source)["status"], "queued")

    def test_corrupt_file_reports_verbatim_ffprobe_stderr_and_never_enters_queue(self):
        self.source.write_bytes(b"not an MP4 recording")
        os.utime(self.source, (1, 1))
        captured = []
        original_run = subprocess.run

        def capture_probe(*args, **kwargs):
            result = original_run(*args, **kwargs)
            captured.append(result)
            return result

        with patch("source_validation.subprocess.run", side_effect=capture_probe):
            with self.assertRaises(SourceValidationError) as raised:
                self.store.enqueue(self.source)
        actual = captured[0]
        self.assertNotEqual(actual.returncode, 0)
        self.assertEqual(raised.exception.stderr, actual.stderr)
        self.assertIn(actual.stderr, str(raised.exception))
        self.assertEqual(self.store.list(), [])
        report = next((self.root / "AutomationLogs/rejected-inputs").glob("*.json"))
        self.assertEqual(json.loads(report.read_text())["ffprobe_stderr"], actual.stderr)

    def test_empty_and_audio_only_inputs_are_rejected(self):
        for contents in (b"", self.audio_bytes):
            with self.subTest(size=len(contents)):
                self.source.write_bytes(contents)
                os.utime(self.source, (1, 1))
                with self.assertRaises(SourceValidationError):
                    self.store.enqueue(self.source)
                self.assertEqual(self.store.list(), [])

    def test_manual_enqueue_cli_reports_probe_error_without_creating_a_job(self):
        self.source.write_bytes(b"corrupt input")
        os.utime(self.source, (1, 1))
        result = subprocess.run(
            [
                os.sys.executable,
                str(Path(automation.__file__).with_name("start.py")),
                "--enqueue",
                "--source",
                str(self.source),
            ],
            env=dict(os.environ, GAMING_SHORTS_HOME=str(self.root)),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("moov atom not found", result.stderr)
        self.assertEqual(self.store.list(), [])
        self.assertFalse((self.root / "Projects").exists())

    def test_watcher_reports_bad_input_once_and_continues_with_valid_video(self):
        bad = self.source.parent / "a-broken.mp4"
        bad.write_bytes(b"broken input")
        os.utime(bad, (1, 1))
        discovery = automation.Discovery(0)
        discovery.scan(self.store)
        error_output = io.StringIO()
        with redirect_stderr(error_output):
            self.assertEqual(len(discovery.scan(self.store)), 1)
            self.assertEqual(discovery.scan(self.store), [])
        output = error_output.getvalue()
        self.assertEqual(output.count("Rejected input; not queued:"), 1)
        self.assertIn("moov atom not found", output)
        self.assertEqual([job["source"] for job in self.store.list()], [str(self.source)])

    def test_repaired_input_can_be_discovered_after_it_settles_again(self):
        self.source.write_bytes(b"bad recording")
        os.utime(self.source, (1, 1))
        discovery = automation.Discovery(0)
        discovery.scan(self.store)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(discovery.scan(self.store), [])
        self.source.write_bytes(self.video_bytes)
        os.utime(self.source, (1, 1))
        self.assertEqual(discovery.scan(self.store), [])
        self.assertEqual(len(discovery.scan(self.store)), 1)

    def test_requeue_also_requires_probe_success_without_changing_status(self):
        job = self.store.enqueue(self.source)
        self.store.claim()
        self.store.finish(job["id"], "needs_attention")
        error = SourceValidationError("actual FFprobe failure", stderr="actual FFprobe failure")
        with patch.object(self.store, "admit_source", side_effect=error):
            with self.assertRaisesRegex(SourceValidationError, "actual FFprobe failure"):
                self.store.retry(job["id"])
        self.assertEqual(self.store.get(job["id"])["status"], "needs_attention")

    def test_probe_timeout_diagnostic_is_preserved(self):
        timeout = subprocess.TimeoutExpired("ffprobe", 60, stderr=b"specific probe diagnostic\n")
        with patch("source_validation.subprocess.run", side_effect=timeout):
            with self.assertRaisesRegex(SourceValidationError, "specific probe diagnostic"):
                inspect_source(self.source)

    def test_source_mutation_during_probe_is_rejected(self):
        original_run = subprocess.run

        def probe_then_mutate(*args, **kwargs):
            result = original_run(*args, **kwargs)
            self.source.write_bytes(self.video_bytes + b"\0")
            return result

        with patch("source_validation.subprocess.run", side_effect=probe_then_mutate):
            with self.assertRaisesRegex(SourceValidationError, "changed while FFprobe"):
                self.store.enqueue(self.source)
        self.assertEqual(self.store.list(), [])
