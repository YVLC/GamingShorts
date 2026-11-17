import json, tempfile, unittest, sys, wave, array
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common, gaming_shorts as gs, editorial, captions, music_library, publication
from audio_checks import indicators
from test_regressions import plan, tone


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = gs.ROOT
        gs.ROOT = self.root
        self.p = self.root / "project"
        self.p.mkdir()
        common.save(
            self.p / "manifest.json",
            {"source": str(self.root / "source.mp4"), "source_sha256": "test", "duration": 60},
        )
        common.save(self.p / "edit_plan.json", plan())

    def tearDown(self):
        gs.ROOT = self.old
        self.tmp.cleanup()

    def test_ranges_remain_reserved_after_rejection(self):
        editorial.remember(self.p, "validated")
        editorial.remember(self.p, "rejected", "New style please")
        other = self.root / "other"
        other.mkdir()
        common.save(other / "manifest.json", common.read(self.p / "manifest.json"))
        with self.assertRaisesRegex(ValueError, "overlaps"):
            editorial.check_ranges(other, plan())

    def test_self_overlap_rejected(self):
        d = plan()
        d["clips"][1]["start"] = 1
        with self.assertRaisesRegex(ValueError, "within"):
            editorial.check_ranges(self.p, d)

    def test_structure_rotation(self):
        old = plan()
        old["editorial"]["structure"] = "close_call"
        common.save(self.p / "edit_plan.json", old)
        editorial.remember(self.p, "validated")
        new = plan()
        new["clips"][0]["narration"] = "A hidden door changes the entire route."
        new["editorial"].update(
            premise="Door discovery opens an entirely different path",
            structure="close_call",
            beats=["door appears", "door opens", "path revealed"],
        )
        new["clips"][-1]["narration"] = "Subscribe for more."
        with self.assertRaisesRegex(ValueError, "Narrative structure"):
            editorial.check_blueprint(self.root / "other", new)

    def test_distinct_candidate_structures(self):
        with self.assertRaisesRegex(ValueError, "different narrative"):
            editorial.check_candidates({"candidates": [{"structure": "close_call"}] * 3})

    def test_words_cannot_be_fabricated_from_phrase(self):
        with self.assertRaises(ValueError):
            captions.validate_words([], "Hello there", 2)
        with self.assertRaises(ValueError):
            captions.validate_words([{"word": "wrong", "start": 0, "end": 1}], "Hello there", 2)

    def test_word_overlap_nan_and_end_rejected(self):
        for a, b in ((0, float("nan")), (0.8, 0.5), (0, 3)):
            with self.assertRaises(ValueError):
                captions.validate_words([{"word": "Hello", "start": a, "end": b}], "Hello", 2)
        with self.assertRaises(ValueError):
            captions.validate_words(
                [
                    {"word": "Hello", "start": 0, "end": 1},
                    {"word": "there", "start": 0.5, "end": 1.5},
                ],
                "Hello there",
                2,
            )

    def test_ass_highlight_and_srt_final_time(self):
        words = [
            {"word": "Hello", "start": 0.1, "end": 0.5},
            {"word": "there.", "start": 0.6, "end": 1},
        ]
        captions.validate_words(words, "Hello there.", 2)
        out = self.root / "line.ass"
        captions.write_ass(out, words, 720, 1280, 0.2)
        self.assertIn("&H00FFFF&", out.read_text())
        self.assertIn("0:00:00.30", out.read_text())
        self.assertIn("Hello", out.read_text())
        captions.sidecars(self.root, [{"words": words}], [5.2])
        self.assertIn("00:00:05,300", (self.root / "subtitles.srt").read_text())

    def test_music_rotate_and_pin_by_content(self):
        tracks = []
        for n in range(2):
            audio = self.root / f"{n}.wav"
            tone(audio, 1 + n)
            evidence = self.root / f"{n}.txt"
            evidence.write_text("Test-only licence evidence")
            tracks.append(
                {
                    "id": str(n),
                    "path": str(audio),
                    "license": "test fixture",
                    "title": "Test track", "artist": "Fixture", "source": "fixture",
                    "genre": "electronic", "mood": "suspense", "energy": .5,
                    "approval_status": "approved", "usage_route": "cleared",
                    "permitted_use": "youtube_ugc", "attribution": "Fixture credit",
                    "approved_audio_sha256": common.digest(audio),
                    "approved_evidence_sha256": common.digest(evidence),
                    "license_evidence": str(evidence),
                    "source_url": "test fixture",
                }
            )
        catalog = self.root / "catalog.json"
        common.save(catalog, {"tracks": tracks})
        cfg = dict(common.config(), music_rotation=True,music_strategy="library", music_catalog=str(catalog))
        with patch.object(music_library, "config", return_value=cfg):
            a = music_library.select(self.p)
            other = self.root / "other"
            other.mkdir()
            common.save(other / "edit_plan.json", plan())
            b = music_library.select(other)
            self.assertNotEqual(a["sha256"], b["sha256"])
            self.assertEqual(a, music_library.select(self.p))
            tracks[1]["path"] = tracks[0]["path"]
            common.save(catalog, {"tracks": tracks})
            # Duplicate audio cannot create two rotation entries. Changed bytes
            # under an existing approval fail validation until explicitly approved.
            with self.assertRaisesRegex(ValueError, "changed"):
                music_library.catalog()

    def test_music_missing_license_blocks(self):
        cat = self.root / "catalog.json"
        common.save(cat, {"tracks": [{"id": "missing"}]})
        with patch.object(music_library, "config", return_value={"music_catalog": str(cat)}):
            with self.assertRaises(ValueError):
                music_library.catalog()

    def test_publication_rejects_private_wrong_file_pending(self):
        final = self.root / "output.mp4"
        final.write_bytes(b"test")
        item = {
            "id": "abcdefghijk",
            "snippet": {"channelId": "channel"},
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "processingDetails": {"processingStatus": "succeeded"},
            "fileDetails": {"fileName": final.name, "fileSize": "4"},
        }
        self.assertTrue(publication.validate_remote(item, "abcdefghijk", "channel", final))
        for section, field, value in [
            ("status", "privacyStatus", "private"),
            ("processingDetails", "processingStatus", "processing"),
            ("fileDetails", "fileSize", "3"),
            ("snippet", "channelId", "wrong"),
        ]:
            bad = json.loads(json.dumps(item))
            bad[section][field] = value
            with self.assertRaises(ValueError):
                publication.validate_remote(bad, "abcdefghijk", "channel", final)

    def test_cleanup_requires_committed_publication(self):
        final = self.root / "output.mp4"
        final.write_bytes(b"test")
        common.save(
            self.p / "qc_report.json",
            {"output": str(final), "output_sha256": common.digest(final), "input_key": "abc"},
        )
        with self.assertRaisesRegex(RuntimeError, "committed"):
            publication.cleanup(self.p, True)
        self.assertTrue(final.exists())

    def test_cleanup_keeps_original_audio_and_symlinks(self):
        final = self.root / "output.mp4"
        final.write_bytes(b"test")
        sha = common.digest(final)
        common.save(
            self.p / "qc_report.json",
            {"output": str(final), "output_sha256": sha, "input_key": "abc"},
        )
        with editorial.connect() as db:
            db.execute(
                "CREATE TABLE publications (project TEXT,output_sha256 TEXT,evidence_json TEXT)"
            )
            db.execute(
                "INSERT INTO publications VALUES (?,?,?)",
                (str(self.p.resolve()), sha, json.dumps({"input_key": "abc"})),
            )
        renders = self.p / "Renders/abc"
        renders.mkdir(parents=True)
        (renders / "shot_01.mp4").write_bytes(b"temp")
        (renders / "speech.wav").symlink_to(final)
        (renders / "subtitles.srt").write_text("keep")
        publication.cleanup(self.p, True)
        self.assertFalse((renders / "shot_01.mp4").exists())
        self.assertTrue(final.exists())
        self.assertTrue((renders / "subtitles.srt").exists())
        self.assertTrue((renders / "speech.wav").is_symlink())

    def test_impulse_detection_does_not_modify_audio(self):
        samples = [0] * 100
        samples[50] = 25000
        before = list(samples)
        self.assertEqual(len(indicators(samples)["possible_impulse_seconds"]), 1)
        self.assertEqual(samples, before)


if __name__ == "__main__":
    unittest.main()
