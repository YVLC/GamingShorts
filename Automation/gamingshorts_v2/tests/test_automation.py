"""Queue behavior under restarts, changing inputs, rejection and failed children."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import automation
import common
import gaming_shorts as gs
from job_store import JobStore
import start
from test_regressions import plan


class AutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "fixture.mp4"
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

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous_root = gs.ROOT
        gs.ROOT = self.root
        self.source = self.root / "Sources" / "recording.mp4"
        self.source.parent.mkdir()
        self.source.write_bytes(self.video_bytes)
        os.utime(self.source, (1, 1))
        self.store = JobStore(self.root)

    def tearDown(self):
        gs.ROOT = self.previous_root
        self.tmp.cleanup()

    def queued(self, stop_after=None):
        self.store.enqueue(self.source, stop_after=stop_after)
        return self.store.claim()

    def prepare_fixture(self):
        project = start.project_for(self.source)
        metadata = self.source.stat()
        common.save(
            project / "manifest.json",
            {
                "source": str(self.source),
                "source_sha256": common.digest(self.source),
                "duration": 90,
                "source_size_bytes": metadata.st_size,
                "source_modified_ns": metadata.st_mtime_ns,
            },
        )
        common.save(project / "edit_plan.json", plan())
        return project

    def test_enqueue_is_idempotent_across_restarts(self):
        first = self.store.enqueue(self.source, stop_after="plan")
        second = JobStore(self.root).enqueue(self.source)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["stop_after"], "plan")
        self.assertEqual(len(self.store.list()), 1)

    def test_claim_does_not_claim_the_same_job_twice(self):
        job = self.queued()
        self.assertEqual(job["attempts"], 1)
        self.assertIsNone(JobStore(self.root).claim())

    def test_restart_requires_attention_and_never_requeues(self):
        job = self.queued()
        reopened = JobStore(self.root)
        self.assertEqual(reopened.recover_interrupted(), 1)
        self.assertEqual(reopened.get(job["id"])["status"], "needs_attention")
        self.assertIsNone(reopened.claim())

    def test_explicit_resume_can_promote_plan_to_full_workflow(self):
        job = self.queued("plan")
        self.store.finish(job["id"], "planned")
        resumed = self.store.retry(job["id"])
        self.assertEqual(resumed["status"], "queued")
        self.assertIsNone(resumed["stop_after"])

    def test_changed_source_cannot_be_resumed(self):
        job = self.queued()
        self.store.finish(job["id"], "needs_attention")
        self.source.write_bytes(b"different recording")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            self.store.retry(job["id"])

    def test_changed_source_is_blocked_before_launch(self):
        job = self.queued()
        self.source.write_bytes(b"different recording")
        with (
            patch.object(start, "prepare") as prepare,
            patch.object(automation.subprocess, "run") as run,
        ):
            automation.run_job(self.store, job)
        prepare.assert_not_called()
        run.assert_not_called()
        self.assertEqual(self.store.get(job["id"])["status"], "needs_attention")

    def test_discovery_requires_a_full_stable_observation_window(self):
        discovery = automation.Discovery(60)
        with patch.object(automation.time, "monotonic", return_value=0):
            self.assertEqual(discovery.scan(self.store), [])
        with patch.object(automation.time, "monotonic", return_value=59):
            self.assertEqual(discovery.scan(self.store), [])
        with patch.object(automation.time, "monotonic", return_value=60):
            self.assertEqual(len(discovery.scan(self.store)), 1)
        with patch.object(automation.time, "monotonic", return_value=120):
            self.assertEqual(discovery.scan(self.store), [])

    def test_copy_growth_resets_stability_window(self):
        discovery = automation.Discovery(60)
        with patch.object(automation.time, "monotonic", return_value=0):
            discovery.scan(self.store)
        self.source.write_bytes(self.video_bytes + b"\0" * 16)
        os.utime(self.source, (1, 1))
        with patch.object(automation.time, "monotonic", return_value=70):
            self.assertEqual(discovery.scan(self.store), [])
        with patch.object(automation.time, "monotonic", return_value=129):
            self.assertEqual(discovery.scan(self.store), [])
        with patch.object(automation.time, "monotonic", return_value=130):
            self.assertEqual(len(discovery.scan(self.store)), 1)

    def test_existing_and_legacy_projects_are_not_discovered(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                project = (
                    self.root / "Projects/Automated" / start.slug(self.source.name)
                    if legacy
                    else start.project_for(self.source)
                )
                project.mkdir(parents=True, exist_ok=True)
                common.save(project / "manifest.json", {})
                discovery = automation.Discovery(0)
                discovery.scan(self.store)
                self.assertEqual(discovery.scan(self.store), [])
        self.assertEqual(self.store.list(), [])

    def test_failed_child_is_not_retried_by_worker(self):
        self.prepare_fixture()
        self.store.enqueue(self.source)
        calls = []

        def child(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 1)

        automation.work(self.store, runner=child)
        automation.work(self.store, runner=child)
        self.assertEqual(len(calls), 1)
        job = self.store.list()[0]
        self.assertEqual(job["status"], "needs_attention")
        self.assertTrue(Path(job["log"]).is_file())
        self.assertNotIn("--retry-voice", calls[0])
        self.assertNotIn("--new-voice", calls[0])

    def test_success_exit_without_output_is_not_ready(self):
        self.prepare_fixture()
        job = self.queued()
        automation.run_job(
            self.store,
            job,
            runner=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
        )
        self.assertEqual(self.store.get(job["id"])["status"], "needs_attention")

    def test_busy_manual_workflow_does_not_consume_queued_jobs(self):
        job = self.store.enqueue(self.source)
        with common.locked(self.root / "Database/.workflow_v2.lock"):
            with patch.object(automation.subprocess, "run") as run:
                automation.work(self.store)
        run.assert_not_called()
        self.assertEqual(self.store.get(job["id"])["status"], "queued")

    def test_rejected_project_is_not_rerun(self):
        project = self.prepare_fixture()
        common.state(project, "rejected", reason="Repeated hook")
        job = self.queued()
        run = Mock()
        automation.run_job(self.store, job, runner=run)
        run.assert_not_called()
        self.assertEqual(common.read(project / "state.json")["stage"], "rejected")

    def test_real_child_plan_only_never_requests_speech(self):
        self.prepare_fixture()
        job = self.queued("plan")
        with patch.dict(os.environ, {"GAMING_SHORTS_HOME": str(self.root)}):
            automation.run_job(self.store, job)
        result = self.store.get(job["id"])
        self.assertEqual(result["status"], "planned", Path(result["log"]).read_text())
        self.assertFalse((Path(result["project"]) / "VoiceVersions").exists())

    def test_queue_and_project_actions_cannot_be_combined(self):
        with patch.object(start.sys, "argv", ["start.py", "--queue", "--approve"]):
            with self.assertRaises(SystemExit) as raised:
                start.main()
        self.assertEqual(raised.exception.code, 2)
