"""Content deduplication, packet/decode integrity, migration and crash isolation."""

import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import automation
import common
import gaming_shorts as gs
from job_store import JobStore
from source_validation import SourceValidationError, checked_decode, decode_source, inspect_source
import start
from test_regressions import plan


class IntegrityPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "faststart.mp4"
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
                    "testsrc2=s=96x64:r=10:d=2",
                    "-c:v",
                    "libx264",
                    "-movflags",
                    "+faststart",
                    str(path),
                ],
                check=True,
            )
            cls.video_bytes = path.read_bytes()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "Sources/a-recording.mp4"
        self.source.parent.mkdir()
        self.write(self.source, self.video_bytes)
        self.old_root = gs.ROOT
        gs.ROOT = self.root
        self.store = JobStore(self.root)

    def tearDown(self):
        gs.ROOT = self.old_root
        self.tmp.cleanup()

    def write(self, path, contents):
        path.write_bytes(contents)
        os.utime(path, (1, 1))

    def project(self, source=None, variant="main"):
        source = source or self.source
        folder = start.project_for(source, variant)
        stat = source.stat()
        common.save(
            folder / "manifest.json",
            {
                "source": str(source),
                "source_sha256": common.digest(source),
                "duration": 90,
                "source_size_bytes": stat.st_size,
                "source_modified_ns": stat.st_mtime_ns,
            },
        )
        common.save(folder / "edit_plan.json", plan())
        return folder

    def test_missing_moov_is_rejected_with_actual_diagnostic(self):
        # A real ftyp+mdat file without its moov, not merely an invalid extension.
        self.write(
            self.source,
            struct.pack(">I4s4sI4s", 20, b"ftyp", b"isom", 0, b"isom")
            + struct.pack(">I4s", 16, b"mdat")
            + b"\0" * 8,
        )
        with self.assertRaisesRegex(SourceValidationError, "moov atom not found") as raised:
            self.store.enqueue(self.source)
        self.assertIn("moov atom not found", raised.exception.stderr)
        self.assertEqual(self.store.list(), [])

    def test_faststart_truncation_with_intact_metadata_is_rejected(self):
        self.assertLess(self.video_bytes.index(b"moov"), self.video_bytes.index(b"mdat"))
        self.write(self.source, self.video_bytes[:-80])
        with self.assertRaises(SourceValidationError):
            self.store.enqueue(self.source)
        self.assertEqual(self.store.list(), [])

    def test_content_duplicates_return_same_job_across_paths_and_restarts(self):
        first = self.store.enqueue(self.source)
        copy = self.source.with_name("renamed-copy.mp4")
        self.write(copy, self.video_bytes)
        second = JobStore(self.root).enqueue(copy)
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["duplicate_submission"])
        self.assertEqual(second["submitted_source"], str(copy))
        self.assertEqual(len(self.store.list()), 1)

    def test_explicit_variants_remain_supported(self):
        first = self.store.enqueue(self.source)
        second = self.store.enqueue(self.source, variant="second")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["source_sha256"], second["source_sha256"])

    def test_duplicate_submission_race_has_only_one_canonical_row(self):
        from concurrent.futures import ThreadPoolExecutor

        copy = self.source.with_name("copy.mp4")
        self.write(copy, self.video_bytes)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(lambda path: JobStore(self.root).enqueue(path), [self.source, copy])
            )
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(len(self.store.list()), 1)

    def test_renamed_copy_of_prequeue_project_does_not_create_a_new_job(self):
        project = self.project()
        common.state(project, "published")
        copy = self.source.with_name("renamed-published.mp4")
        self.write(copy, self.video_bytes)
        before = {str(path): path.read_bytes() for path in project.rglob("*") if path.is_file()}
        result = self.store.enqueue(copy)
        self.assertEqual(result["status"], "existing_project")
        self.assertEqual(result["project"], str(project))
        self.assertEqual(self.store.list(), [])
        self.assertEqual(
            before, {str(path): path.read_bytes() for path in project.rglob("*") if path.is_file()}
        )

    def test_explicit_new_variant_of_prequeue_project_is_still_allowed(self):
        self.project()
        copy = self.source.with_name("explicit-variant.mp4")
        self.write(copy, self.video_bytes)
        result = self.store.enqueue(copy, variant="second")
        self.assertEqual(result["status"], "queued")

    def test_repeated_enqueue_reuses_admission_receipt_without_hashing(self):
        first = self.store.enqueue(self.source)
        with (
            patch("job_store.digest", side_effect=AssertionError("unnecessary full hash")),
            patch(
                "job_store.inspect_source", side_effect=AssertionError("unnecessary packet scan")
            ),
        ):
            self.assertEqual(self.store.enqueue(self.source)["id"], first["id"])

    def test_processing_verifies_checksum_then_decodes_once_across_retries(self):
        self.store.enqueue(self.source)
        job = self.store.claim()
        real_hash = common.digest
        with (
            patch("job_store.digest", wraps=real_hash) as hashes,
            patch("job_store.decode_source", wraps=decode_source) as decodes,
        ):
            self.store.processing_source(job)
            self.assertEqual(hashes.call_count, 1)
            self.assertEqual(decodes.call_count, 1)
        self.store.finish(job["id"], "needs_attention")
        self.store.retry(job["id"])
        with (
            patch("job_store.digest", side_effect=AssertionError("repeat full hash")),
            patch("job_store.decode_source", side_effect=AssertionError("repeat full decode")),
        ):
            self.store.processing_source(self.store.claim())

    def test_decode_receipt_reused_for_identical_content_in_explicit_variant(self):
        first = self.store.enqueue(self.source)
        self.store.processing_source(self.store.claim())
        self.store.finish(first["id"], "planned")
        copy = self.source.with_name("variant-copy.mp4")
        self.write(copy, self.video_bytes)
        self.store.enqueue(copy, variant="second")
        with patch("job_store.decode_source", side_effect=AssertionError("duplicate decode")):
            self.store.processing_source(self.store.claim())

    def test_same_size_change_with_restored_mtime_stops_before_processing(self):
        job = self.store.enqueue(self.source)
        replacement = bytearray(self.video_bytes)
        replacement[-1] ^= 1
        self.write(self.source, replacement)
        runner = Mock()
        automation.run_job(self.store, self.store.claim(), runner)
        runner.assert_not_called()
        self.assertEqual(self.store.get(job["id"])["status"], "needs_attention")

    def test_checksum_mismatch_stops_before_decode_or_planning(self):
        job = self.store.enqueue(self.source)
        runner = Mock()
        with (
            patch("job_store.digest", return_value="0" * 64),
            patch("job_store.decode_source") as decode,
        ):
            automation.run_job(self.store, self.store.claim(), runner)
        decode.assert_not_called()
        runner.assert_not_called()
        self.assertIn("checksum changed", self.store.get(job["id"])["error"])

    def test_invalid_recording_does_not_block_next_queued_job(self):
        broken = self.store.enqueue(self.source, stop_after="plan")
        self.write(self.source, b"changed broken media")
        healthy = self.source.with_name("b-healthy.mp4")
        self.write(healthy, self.video_bytes + b"\0" * 8)
        valid = self.store.enqueue(healthy, stop_after="plan")
        self.project(healthy)

        def child(command, **kwargs):
            return subprocess.CompletedProcess(command, 0)

        automation.work(self.store, runner=child)
        self.assertEqual(self.store.get(broken["id"])["status"], "needs_attention")
        self.assertEqual(self.store.get(valid["id"])["status"], "planned")

    def test_actual_ffmpeg_stderr_is_captured(self):
        _, _, document = inspect_source(self.source, details=True)
        self.write(self.source, b"corrupt MP4")
        with self.assertRaises(SourceValidationError) as raised:
            decode_source(self.source, document)
        self.assertIn("moov atom not found", raised.exception.stderr)
        self.assertIn(raised.exception.stderr, str(raised.exception))
        self.assertEqual(raised.exception.tool, "FFmpeg")

    def test_stalled_decoder_is_killed_and_actual_stderr_is_preserved(self):
        command = [
            os.sys.executable,
            "-c",
            "import sys,time; sys.stderr.write('decoder-specific failure\\n'); sys.stderr.flush(); time.sleep(10)",
        ]
        with self.assertRaisesRegex(SourceValidationError, "FFmpeg stalled") as raised:
            checked_decode(command, timeout=5, stall_seconds=0.2)
        self.assertEqual(raised.exception.stderr, "decoder-specific failure\n")

    def test_decode_overall_deadline_is_bounded(self):
        command = [os.sys.executable, "-c", "import time; time.sleep(10)"]
        with self.assertRaisesRegex(SourceValidationError, "FFmpeg timed out"):
            checked_decode(command, timeout=0.2, stall_seconds=5)

    def test_interruption_kills_decoder_subprocess(self):
        processes = []
        actual_popen = subprocess.Popen

        def launch(*args, **kwargs):
            process = actual_popen(*args, **kwargs)
            processes.append(process)
            return process

        with (
            patch("source_validation.subprocess.Popen", side_effect=launch),
            patch(
                "source_validation.selectors.EpollSelector.select", side_effect=KeyboardInterrupt
            ),
        ):
            with self.assertRaises(KeyboardInterrupt):
                checked_decode([os.sys.executable, "-c", "import time; time.sleep(10)"], 5, 5)
        self.assertIsNotNone(processes[0].poll())

    def test_decode_failure_is_persisted_and_later_job_continues(self):
        bad = self.store.enqueue(self.source, stop_after="plan")
        other = self.source.with_name("b-other.mp4")
        self.write(other, self.video_bytes + b"\0" * 8)
        good = self.store.enqueue(other, stop_after="plan")
        self.project(other)
        actual_decode = decode_source
        diagnostic = "[h264] corrupt decoded frame\nError while decoding stream #0:0\n"

        def decode(path, document):
            if path == self.source:
                raise SourceValidationError(
                    "FFmpeg rejected recording:\n" + diagnostic,
                    stderr=diagnostic,
                    returncode=1,
                    tool="FFmpeg",
                )
            return actual_decode(path, document)

        with patch("job_store.decode_source", side_effect=decode):
            automation.work(
                self.store, runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0)
            )
        result = self.store.get(bad["id"])
        self.assertIn(diagnostic, result["error"])
        self.assertIn(diagnostic, Path(result["log"]).read_text())
        self.assertEqual(self.store.get(good["id"])["status"], "planned")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM decoded_sources").fetchone()[0], 1)

    def test_interrupted_decode_never_saves_success_and_requires_explicit_resume(self):
        job = self.store.enqueue(self.source)
        with patch("job_store.decode_source", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                automation.run_job(self.store, self.store.claim(), runner=Mock())
        reopened = JobStore(self.root)
        self.assertEqual(reopened.get(job["id"])["status"], "needs_attention")
        self.assertIsNone(reopened.claim())
        with reopened.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM decoded_sources").fetchone()[0], 0)
        reopened.retry(job["id"])
        reopened.processing_source(reopened.claim())

    def test_interrupted_hash_never_inserts_queue_or_successful_cache_entry(self):
        with patch("job_store.digest", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.store.enqueue(self.source)
        self.assertEqual(self.store.list(), [])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM source_checks").fetchone()[0], 0)

    def test_prepare_reuses_verified_worker_digest(self):
        self.store.enqueue(self.source)
        proof = self.store.processing_source(self.store.claim())
        with (
            patch.object(gs, "duration", return_value=90),
            patch.object(start, "digest", side_effect=AssertionError("redundant manifest hash")),
        ):
            folder = start.prepare(self.source, verified_source=proof)
        self.assertEqual(common.read(folder / "manifest.json")["source_sha256"], proof["sha256"])

    def test_source_changing_during_checksum_never_enters_queue(self):
        def hash_then_change(path):
            value = common.digest(path)
            self.write(path, self.video_bytes + b"\0" * 8)
            return value

        with patch("job_store.digest", side_effect=hash_then_change):
            with self.assertRaisesRegex(SourceValidationError, "changed during checksum"):
                self.store.enqueue(self.source)
        self.assertEqual(self.store.list(), [])

    def test_recent_manual_input_is_deferred_without_probe(self):
        os.utime(self.source, None)
        with patch("job_store.inspect_source") as inspect:
            with self.assertRaisesRegex(SourceValidationError, "still settling"):
                self.store.enqueue(self.source)
        inspect.assert_not_called()

    def test_decode_failure_does_not_create_success_receipt(self):
        self.store.enqueue(self.source)

        def decode_then_change(path, document):
            receipt = decode_source(path, document)
            self.write(path, self.video_bytes + b"\0" * 8)
            return receipt

        with patch("job_store.decode_source", side_effect=decode_then_change):
            with self.assertRaisesRegex(SourceValidationError, "changed during decode"):
                self.store.processing_source(self.store.claim())
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM decoded_sources").fetchone()[0], 0)
            self.assertIsNone(db.execute("SELECT processing_key FROM source_checks").fetchone()[0])

    def test_changed_decoder_binary_invalidates_success_receipt(self):
        job = self.store.enqueue(self.source)
        self.store.processing_source(self.store.claim())
        self.store.finish(job["id"], "needs_attention")
        self.store.retry(job["id"])
        from source_validation import validator_key

        def changed_key(tool):
            return "changed-ffmpeg-policy" if tool == "ffmpeg" else validator_key(tool)

        with (
            patch("job_store.validator_key", side_effect=changed_key),
            patch("job_store.decode_source", wraps=decode_source) as decode,
        ):
            self.store.processing_source(self.store.claim())
        self.assertEqual(decode.call_count, 1)

    def test_unknown_codec_and_zero_duration_are_rejected(self):
        _, _, original = inspect_source(self.source, details=True)
        for change in ("codec", "duration"):
            document = json.loads(json.dumps(original))
            if change == "codec":
                document["streams"][0]["codec_name"] = "unknown"
            else:
                document["format"]["duration"] = "0"
                for stream in document["streams"]:
                    stream["duration"] = "0"
            result = subprocess.CompletedProcess([], 0, json.dumps(document), "")
            with (
                self.subTest(change=change),
                patch("source_validation.subprocess.run", return_value=result),
            ):
                with self.assertRaises(SourceValidationError):
                    self.store.enqueue(self.source)
            self.assertEqual(self.store.list(), [])

    def test_legacy_duplicate_is_preserved_as_a_nonrunnable_history_row(self):
        canonical = self.store.enqueue(self.source)
        self.store.finish(canonical["id"], "planned")
        copy = self.source.with_name("legacy-copy.mp4")
        self.write(copy, self.video_bytes)
        stat = copy.stat()
        with self.store.connect() as db:
            db.execute(
                """INSERT INTO jobs
                (id,source,variant,size,modified_ns,status,created_utc,updated_utc)
                VALUES (?,?,?,?,?,'queued',?,?)""",
                (
                    "legacy-duplicate",
                    str(copy),
                    "main",
                    stat.st_size,
                    stat.st_mtime_ns,
                    "old",
                    "old",
                ),
            )
        with patch(
            "job_store.decode_source", side_effect=AssertionError("decode of old duplicate")
        ):
            proof = self.store.processing_source(self.store.claim())
        self.assertEqual(proof["duplicate_of"], canonical["id"])
        self.assertEqual(self.store.get("legacy-duplicate")["status"], "duplicate")
        self.assertEqual(len(self.store.list()), 2)
        self.assertIsNone(self.store.claim())
        self.assertEqual(copy.read_bytes(), self.video_bytes)

    def test_approved_project_and_its_files_are_never_changed(self):
        folder = self.project()
        common.state(folder, "approved")
        for name in ("approval.json", "Voices/line_01.wav", "Renders/old/final.mp4"):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"user-approved-fixture")
        before = {str(path): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        self.store.enqueue(self.source)
        with patch(
            "job_store.decode_source", side_effect=AssertionError("approved project decode")
        ):
            automation.work(self.store, runner=Mock())
        after = {str(path): path.read_bytes() for path in folder.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_old_queue_schema_migrates_without_replacing_rows(self):
        legacy_root = self.root / "legacy"
        (legacy_root / "Database").mkdir(parents=True)
        path = legacy_root / "Database/automation.sqlite3"
        stat = self.source.stat()
        with sqlite3.connect(path) as db:
            db.execute("""CREATE TABLE jobs (id TEXT PRIMARY KEY,source TEXT NOT NULL,variant TEXT NOT NULL,
                size INTEGER NOT NULL,modified_ns INTEGER NOT NULL,stop_after TEXT,status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,project TEXT,log TEXT,error TEXT,created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL,UNIQUE(source,variant))""")
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "old-id",
                    str(self.source),
                    "main",
                    stat.st_size,
                    stat.st_mtime_ns,
                    "plan",
                    "queued",
                    4,
                    "saved-project",
                    "saved-log",
                    None,
                    "old",
                    "old",
                ),
            )
        migrated = JobStore(legacy_root)
        row = migrated.get("old-id")
        self.assertEqual(
            (row["attempts"], row["project"], row["log"]), (4, "saved-project", "saved-log")
        )
        self.assertIsNone(row["source_sha256"])
        proof = migrated.processing_source(migrated.claim())
        self.assertEqual(migrated.get("old-id")["source_sha256"], proof["sha256"])
        self.assertEqual(migrated.get("old-id")["attempts"], 5)
