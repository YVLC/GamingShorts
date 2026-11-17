"""Full-game catalog/index/editorial regression fixtures. No AI service calls."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import key, read, save
import gaming_shorts as gs
from game_store import GameStore, interval, visually_similar
from job_store import stat_key
import game_index as index
import game_plan
import full_game


class FullGameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(gs, "ROOT", self.root)
        self.root_patch.start()
        source = self.root / "GameSources/cairn/full.mp4"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"fixture original, not video")
        self.proof = {
            "source": str(source),
            "sha256": "source-sha",
            "fingerprint": stat_key(source.stat()),
            "probe": {
                "format": {"duration": "25200"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 3840,
                        "height": 2160,
                        "avg_frame_rate": "60000/1001",
                    }
                ],
            },
        }
        self.store = GameStore()
        self.r = self.store.register("cairn", "Cairn", self.proof)
        self.store.select("cairn")

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def scene(self, identity="scene", a=7200, b=7240, hashes=None, **changes):
        row = {
            "id": identity,
            "recording": self.r["id"],
            "index_key": "index",
            "chunk": 60,
            "start": a,
            "end": b,
            "description": "Climber changes holds on rock",
            "category": "climb",
            "confidence": 0.95,
            "evidence": "Hands reposition visibly",
            "tags_json": '["climb"]',
            "hashes_json": json.dumps(hashes or ["0123456789abcdef"]),
            "score": 0.9,
            "rejected": None,
        }
        row.update(changes)
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO game_scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                tuple(row.values()),
            )
        return row

    def indexed(self):
        with self.store.connect() as db:
            db.execute("UPDATE game_recordings SET status='indexed',index_key='index'")
        self.r = self.store.recording()

    def project(self):
        p = self.root / "Projects/V2/test"
        p.mkdir(parents=True)
        save(
            p / "manifest.json",
            {
                "source": self.r["source"],
                "source_sha256": self.r["sha256"],
                "duration": self.r["duration"],
                "full_game": {
                    "game": "cairn",
                    "recording": self.r["id"],
                    "index_key": "index",
                    "batch": "batch",
                },
            },
        )
        return p

    def test_seven_hours_have_no_gaps_no_first_hour_limit(self):
        windows = list(index.chunks(25200.125))
        self.assertEqual(windows[0], (0, 0, 120))
        self.assertEqual(windows[-1], (210, 25200, 25200.125))
        self.assertEqual(sum(b - a for _, a, b in windows), 25200.125)
        self.assertTrue(all(left[2] == right[1] for left, right in zip(windows, windows[1:])))

    def test_nonfinite_timestamps_rejected(self):
        for a, b in ((float("nan"), 4), (0, float("inf")), (-1, 4), (4, 3), (0, 25201)):
            with self.assertRaises(ValueError):
                interval(a, b, 25200)

    def test_registration_does_not_select_or_replace_source(self):
        other = dict(self.proof, sha256="second")
        with self.assertRaisesRegex(ValueError, "already has"):
            self.store.register("cairn", "Cairn", other)
        self.store.register("another", "Another Game", other)
        self.assertEqual(self.store.recording()["game"], "cairn")
        self.store.select("another")
        self.assertEqual(self.store.recording()["game"], "another")

    def test_source_metadata_and_path_bound(self):
        source = Path(self.r["source"])
        source.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            index.checked_recording(self.r)
        with self.assertRaisesRegex(ValueError, "rebinding"):
            self.store.register(
                "cairn", "Cairn", dict(self.proof, fingerprint=stat_key(source.stat()))
            )

    def test_proxy_folder_cannot_register(self):
        with self.assertRaisesRegex(ValueError, "GameSources"):
            full_game.register("cairn", "Cairn", self.root / "ReviewCopies/proxy.mp4")

    def test_static_unknown_and_bridge_excluded(self):
        for i, change in enumerate(
            (
                {"confidence": 0.6},
                {"category": "map"},
                {"category": "unknown"},
                {"description": "Walking toward a bridge"},
                {"tags_json": '["bridge"]'},
                {"rejected": "Not interesting"},
            )
        ):
            self.assertFalse(self.store.eligible(self.scene(str(i), **change)))
        self.assertTrue(self.store.eligible(self.scene("good")))

    def test_visual_similarity_different_timestamps(self):
        first = self.scene("first")
        second = self.scene("second", a=15000, b=15040, hashes=["0123456789abcdee"])
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO game_shots VALUES (?,?,?,?,?,?)",
                ("old", first["id"], first["recording"], 7201, 7205, first["hashes_json"]),
            )
        self.assertFalse(self.store.eligible(second))
        self.assertTrue(visually_similar(["0000000000000000"], ["000000000000003f"]))
        self.assertFalse(visually_similar(["0000000000000000"], ["ffffffffffffffff"]))

    def test_legacy_footage_reservation_is_respected(self):
        scene = self.scene()
        import editorial

        with editorial.connect() as db:
            db.execute(
                "INSERT INTO footage_reservations VALUES (?,?,?,?,?)",
                ("old", "pk", self.r["sha256"], 7205, 7210),
            )
        self.assertFalse(self.store.eligible(scene))

    def test_reservations_atomic_and_survive_rejection(self):
        scene = self.scene()
        p = self.project()
        invalid = {
            "clips": [
                {"scene_id": "scene", "start": 7201, "duration": 5},
                {"scene_id": "missing", "start": 7210, "duration": 5},
            ]
        }
        with self.assertRaises(ValueError):
            self.store.reserve(p, invalid, [scene])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM game_shots").fetchone()[0], 0)
        plan = {"clips": [{"scene_id": "scene", "start": 7201, "duration": 5}]}
        self.store.reserve(p, plan, [scene])
        self.assertFalse(self.store.eligible(scene))
        self.assertTrue(self.store.eligible(scene, project=p))

    def test_different_original_cannot_bypass_guard(self):
        self.indexed()
        scene = self.scene()
        p = self.project()
        doc = {"clips": [{"scene_id": "scene", "start": 7201, "duration": 5}]}
        self.store.reserve(p, doc, [scene])
        save(
            p / "evidence_review.json",
            {"plan_key": key(doc), "index_key": "index", "inspected": [["scene", 7200, 7240]]},
        )
        game_plan.guard(p, doc)
        changed = dict(doc, clips=[dict(doc["clips"][0], narration="invented")])
        with self.assertRaisesRegex(ValueError, "changed"):
            game_plan.guard(p, changed)
        m = read(p / "manifest.json")
        m["source"] = str(self.root / "ReviewCopies/analysis.mp4")
        save(p / "manifest.json", m)
        with self.assertRaisesRegex(ValueError, "authoritative"):
            game_plan.guard(p, doc)

    def test_inspected_window_alignment_absolute_not_local(self):
        scene = self.scene()
        game_plan.validate_windows(
            [{"scene_id": "scene", "start": 7205, "duration": 5}],
            [scene],
            self.r,
            [("scene", 7200, 7214)],
        )
        with self.assertRaises(ValueError):
            game_plan.validate_windows(
                [{"scene_id": "scene", "start": 5, "duration": 5}],
                [scene],
                self.r,
                [("scene", 7200, 7214)],
            )

        with self.assertRaisesRegex(ValueError, "dense inspection"):
            game_plan.validate_windows(
                [{"scene_id": "scene", "start": 7220, "duration": 5}],
                [scene],
                self.r,
                [("scene", 7200, 7214)],
            )

    def test_contact_sheets_preserve_timestamp_timebase_without_duplicate_frames(self):
        folder = self.root / "sheets"
        folder.mkdir()
        with patch.object(index, "run") as run:
            index.contact_sheets(self.root / "proxy.mp4", folder, 7200, 7205)
        command = run.call_args.args[0]
        graph = command[command.index("-vf") + 1]
        self.assertIn("select='not(mod(n,1))'", graph)
        self.assertIn("settb=AVTB,setpts=PTS-STARTPTS+7200.000000/TB", graph)
        self.assertNotIn("fps=", graph)

    def test_old_project_guard_is_backward_compatible(self):
        p = self.root / "legacy"
        save(p / "manifest.json", {"source": "missing old source"})
        game_plan.guard(p, {})

    def test_selected_source_fake_cadence_rejected_before_speech(self):
        import quality_checks

        p = self.project()
        result = {"active_windows": 3, "cadence_limited": True, "active_updates_per_second": 15}
        with patch.object(quality_checks, "measure_cadence", return_value=result):
            with self.assertRaisesRegex(ValueError, "No speech requested"):
                game_plan.preflight(p, {"clips": [{"start": 7200, "duration": 5}]})

    def test_static_source_is_not_penalized_and_preflight_receipt_reused(self):
        import quality_checks

        p = self.project()
        result = {"active_windows": 0, "cadence_limited": False, "status": "static_or_low_motion"}
        with patch.object(quality_checks, "measure_cadence", return_value=result) as measure:
            game_plan.preflight(p, {"clips": [{"start": 7200, "duration": 5}]})
            game_plan.preflight(p, {"clips": [{"start": 7200, "duration": 5}]})
            self.assertEqual(measure.call_count, 1)
            game_plan.preflight(p, {"clips": [{"start": 7210, "duration": 5}]})
            self.assertEqual(measure.call_count, 2)

    def test_ai_receipt_reuse_and_uncertain_call_not_replayed(self):
        folder = self.root / "calls"
        with patch.object(index.editorial, "ai", return_value={"scenes": []}) as ai:
            one = index.cached_ai(folder, "same", index.SCHEMA, [], "index")
            self.assertEqual(one, index.cached_ai(folder, "same", index.SCHEMA, [], "index"))
            self.assertEqual(ai.call_count, 1)
            index.cached_ai(folder, "changed", index.SCHEMA, [], "index")
            self.assertEqual(ai.call_count, 2)
        with patch.object(index.editorial, "ai", side_effect=RuntimeError("interrupt")) as ai:
            with self.assertRaises(RuntimeError):
                index.cached_ai(folder, "uncertain", index.SCHEMA, [], "index")
            with self.assertRaisesRegex(RuntimeError, "Uncertain"):
                index.cached_ai(folder, "uncertain", index.SCHEMA, [], "index")
            self.assertEqual(ai.call_count, 1)
        index.authorize_analysis_retry(folder)
        with patch.object(index.editorial, "ai", return_value={"scenes": []}) as ai:
            index.cached_ai(folder, "uncertain", index.SCHEMA, [], "index")
            self.assertEqual(ai.call_count, 1)

    def test_ai_receipt_invalidates_on_image_change(self):
        image = self.root / "frame.jpg"
        image.write_bytes(b"first")
        with patch.object(index.editorial, "ai", return_value={"scenes": []}) as ai:
            index.cached_ai(self.root / "calls", "same", index.SCHEMA, [image], "index")
            image.write_bytes(b"changed")
            index.cached_ai(self.root / "calls", "same", index.SCHEMA, [image], "index")
            self.assertEqual(ai.call_count, 2)

    def test_dense_index_crash_requires_retry_and_reuses_completed_chunks(self):
        # Accelerated 3-chunk recording, same orchestration used for 7 hours.
        with self.store.connect() as db:
            db.execute("UPDATE game_recordings SET duration=250")
        calls = []

        def artifacts(r, folder, a, b):
            calls.append(a)
            folder.mkdir(parents=True, exist_ok=True)
            return {"start": a, "end": b, "scene_changes": [], "files": {}}

        fail = [False]

        def ai(folder, *args):
            if "00001" in str(folder) and not fail[0]:
                fail[0] = True
                raise KeyboardInterrupt()
            return {"scenes": []}

        with (
            patch.dict(index.POLICY, {"overlap_seconds": 0}),
            patch.object(index, "verify_integrity"),
            patch.object(index, "make_artifacts", side_effect=artifacts),
            patch.object(index, "cached_ai", side_effect=ai),
            patch.object(index, "validator_key", return_value="binary"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                index.index_recording()
            self.assertEqual(self.store.recording()["status"], "needs_attention")
            with self.assertRaisesRegex(ValueError, "--retry"):
                index.index_recording()
            result = index.index_recording(retry=True)
            self.assertEqual(result["recording"]["status"], "indexed")
            self.assertEqual([c["end"] for c in result["chunks"]], [120, 240, 250])
            self.assertEqual(calls.count(0), 1)
            self.assertEqual(calls.count(120), 2)
            index.index_recording()
            self.assertEqual(calls, [0, 120, 120, 240])

    def test_material_exhausted_does_not_request_ai(self):
        p = self.project()
        with patch.object(index.editorial, "ai") as ai:
            with self.assertRaisesRegex(ValueError, "exhausted"):
                game_plan.shortlist(p, self.r, self.store)
            ai.assert_not_called()

    def test_overlap_covers_every_source_time_and_preserves_global_offsets(self):
        windows = list(index.chunks(25200, 120, 6))
        self.assertEqual(windows[1], (1, 114, 234))
        self.assertEqual(windows[-1][2], 25200)
        self.assertTrue(all(left[2] - right[1] == 6 for left, right in zip(windows, windows[1:])))
        self.assertGreater(windows[-1][1], 25000)

    def test_estimate_streams_no_full_recording_read_and_low_disk_stops(self):
        from collections import namedtuple

        usage = namedtuple("Usage", "total used free")
        with patch.object(Path, "read_bytes", side_effect=AssertionError("full file read")):
            estimate = index.estimate(self.r)
        self.assertLess(estimate["proxy_budget_bytes"], 2 * 1024**3)
        self.assertGreater(estimate["chunks"], 210)
        with patch.object(index.shutil, "disk_usage", return_value=usage(1000, 999, 1)):
            with self.assertRaisesRegex(OSError, "Insufficient"):
                index.require_disk(self.r)

    def test_validation_checkpoint_recovery_reuses_windows(self):
        from job_store import JobStore

        with self.store.connect() as db:
            db.execute("UPDATE game_recordings SET duration=1250")
        r = self.store.recording()
        attempted = []
        failed = [False]

        def decode(source, document, **kwargs):
            attempted.append(kwargs["start"])
            self.assertGreaterEqual(kwargs["timeout"], kwargs["seconds"] * 32)
            if kwargs["start"] > 0 and not failed[0]:
                failed[0] = True
                raise KeyboardInterrupt()
            return {"frames": 36000, "duration_seconds": kwargs["seconds"]}

        with (
            patch.object(JobStore, "admit_source", return_value=self.proof),
            patch.object(index, "validator_key", return_value="decoder"),
            patch.object(index, "decode_source", side_effect=decode),
        ):
            with self.assertRaises(KeyboardInterrupt):
                index.verify_integrity(r)
            index.verify_integrity(r)
            previous = len(attempted)
            index.verify_integrity(r)
            self.assertEqual(len(attempted), previous)
            self.assertEqual(attempted.count(0), 1)
            self.assertEqual(attempted.count(599.5), 2)

    def test_large_sizes_are_64_bit_and_source_never_copied(self):
        from job_store import JobStore
        from common import now

        queue = JobStore(self.root)
        size = 60 * 1024**3
        with queue.connect() as db:
            db.execute(
                "INSERT INTO jobs(id,source,variant,size,modified_ns,status,created_utc,updated_utc) VALUES ('large','original','main',?,1,'queued',?,?)",
                (size, now(), now()),
            )
        self.assertEqual(queue.get("large")["size"], size)

    def test_legacy_prepare_cannot_start_game_source(self):
        import start

        with self.assertRaisesRegex(ValueError, "--v3 batch"):
            start.prepare(Path(self.r["source"]))

    def test_batch_planning_never_calls_voice_and_resume_keeps_completed_plan(self):
        import start
        import voices
        from job_store import JobStore

        self.indexed()
        created = []
        proof = dict(self.proof, stat=Path(self.r["source"]).stat())

        def prepare(source, variant, **kwargs):
            p = self.root / "Projects/V2" / variant
            save(
                p / "manifest.json",
                {
                    "source": str(source),
                    "source_sha256": self.r["sha256"],
                    "duration": 25200,
                    "full_game": kwargs["full_game_context"],
                },
            )
            return p

        fail = [True]

        def planner(p):
            created.append(p.name)
            if p.name.endswith("_2") and fail[0]:
                fail[0] = False
                raise KeyboardInterrupt()
            save(p / "edit_plan.json", {"clips": []})
            save(p / "story_candidates.json", {})

        with (
            patch.object(JobStore, "admit_source", return_value=proof),
            patch.object(start, "prepare", side_effect=prepare),
            patch.object(game_plan, "plan", side_effect=planner),
            patch.object(game_plan, "guard"),
            patch.object(gs, "validate", return_value={}),
            patch.object(voices, "ensure") as voice,
        ):
            with self.assertRaises(KeyboardInterrupt):
                game_plan.create_batch(3)
            with self.store.connect() as db:
                batch = dict(db.execute("SELECT * FROM game_batches").fetchone())
            self.assertEqual(batch["status"], "needs_attention")
            result = game_plan.create_batch(resume=batch["id"])
            self.assertEqual(result["status"], "planned")
            self.assertEqual(len(result["items"]), 3)
            self.assertEqual(sum(x.endswith("_1") for x in created), 1)
            voice.assert_not_called()

    def test_spend_stages_require_explicit_start(self):
        for args in (["index"], ["batch"], ["run", "--batch", "anything"]):
            with self.assertRaises(SystemExit):
                full_game.main(args)

    def test_limits_and_game_ids(self):
        with self.assertRaises(ValueError):
            self.store.register("../cairn", "Cairn", self.proof)
        for count in (0, 4, 100):
            with self.assertRaisesRegex(ValueError, "one to three"):
                game_plan.create_batch(count)

    def test_queue_targeted_claim_does_not_take_other_game_job(self):
        from job_store import JobStore
        from common import now

        queue = JobStore(self.root)
        with queue.connect() as db:
            for identity in ("other", "selected"):
                db.execute(
                    "INSERT INTO jobs(id,source,variant,size,modified_ns,status,created_utc,updated_utc) VALUES (?,?,?,?,?,'queued',?,?)",
                    (identity, identity, identity, 1, 1, now(), now()),
                )
        self.assertEqual(queue.claim_id("selected")["id"], "selected")
        self.assertEqual(queue.get("other")["status"], "queued")
        self.assertIsNone(queue.claim_id("selected"))

    def test_original_digest_receipt_is_scoped_and_detects_changes(self):
        from common import verified_source_receipts, digest

        source = Path(self.r["source"])
        receipt = {
            str(source): {
                "sha256": "verified-hash",
                "fingerprint": json.loads(self.r["fingerprint"]),
            }
        }
        with verified_source_receipts(receipt):
            with patch.object(Path, "open", side_effect=AssertionError("unnecessary scan")):
                self.assertEqual(digest(source), "verified-hash")
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                digest(source)
        self.assertNotEqual(digest(source), "verified-hash")

    def test_close_batch_preserves_reservations_and_unlocks_new_game(self):
        from common import now

        with self.store.connect() as db:
            db.execute(
                "INSERT INTO game_batches VALUES ('stopped','cairn',?,'index',3,'needs_attention','exhausted',?)",
                (self.r["id"], now()),
            )
            db.execute("INSERT INTO game_shots VALUES ('old','scene',?,1,5,'[]')", (self.r["id"],))
        self.assertEqual(
            self.store.close_batch("stopped", "No more worthwhile footage")["status"], "closed"
        )
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM game_shots").fetchone()[0], 1)

    def test_explicit_analysis_retry_archives_failed_review_and_generates_once(self):
        folder = self.root / "calls"
        with patch.object(index.editorial, "ai", return_value={"scenes": []}) as ai:
            index.cached_ai(folder, "prompt", index.SCHEMA, [], "index")
            index.authorize_analysis_retry(folder, include_completed=True)
            index.cached_ai(folder, "prompt", index.SCHEMA, [], "index")
            self.assertEqual(ai.call_count, 2)
        self.assertEqual(len(list(folder.glob("AttemptArchive_*/*/verified.json"))), 1)

    def test_bad_batch_plan_does_not_block_other_jobs(self):
        from common import now
        from job_store import JobStore
        import automation

        self.indexed()
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO game_batches VALUES ('batch','cairn',?,'index',3,'planned',NULL,?)",
                (self.r["id"], now()),
            )
            for i, name in enumerate(("bad", "good2", "good3")):
                p = self.root / "Projects/V2" / name
                save(p / "edit_plan.json", {})
                db.execute(
                    "INSERT INTO game_batch_items VALUES ('batch',?,?,?,NULL)", (i, str(p), "{}")
                )
        queue = JobStore(self.root)

        def enqueue(source, variant):
            with queue.connect() as db:
                db.execute(
                    "INSERT INTO jobs(id,source,variant,size,modified_ns,status,created_utc,updated_utc) VALUES (?,?,?,?,?,'queued',?,?)",
                    (variant, str(source), variant, 1, 1, now(), now()),
                )
            return queue.get(variant)

        def guard(p, doc):
            if p.name == "bad":
                raise ValueError("Unreviewed changed plan")

        def run_job(store, job):
            store.finish(job["id"], "ready_for_review")

        with (
            patch.object(game_plan, "guard", side_effect=guard),
            patch.object(gs, "validate", return_value={}),
            patch.object(JobStore, "enqueue", side_effect=enqueue),
            patch.object(automation, "run_job", side_effect=run_job),
        ):
            result = game_plan.run_batch("batch")
        self.assertEqual(result["status"], "needs_attention")
        self.assertIn("Unreviewed changed plan", result["error"])
        self.assertEqual(len(queue.list()), 2)
        self.assertTrue(all(j["status"] == "ready_for_review" for j in queue.list()))


if __name__ == "__main__":
    unittest.main()
