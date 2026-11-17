import sys, tempfile, unittest, wave, math, array, subprocess
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common, gaming_shorts as gs, voices, editorial, start


def tone(p, seconds=1):
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(
            array.array(
                "h",
                [
                    int(6000 * math.sin(i * 2 * math.pi * 220 / 16000))
                    for i in range(int(seconds * 16000))
                ],
            ).tobytes()
        )


def plan():
    return {
        "editorial": {
            "premise": "A rescue fails at the ledge",
            "structure": "rescue",
            "payoff": "fall",
        },
        "clips": [
            {
                "start": i * 5,
                "duration": 5,
                "caption": "The ledge broke",
                "narration": "The ledge broke under her feet."
                if i == 0
                else "She reaches for the rope.",
            }
            for i in range(5)
        ],
    }


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = gs.ROOT
        gs.ROOT = self.root
        self.p = self.root / "project"
        self.p.mkdir()
        common.save(
            self.p / "manifest.json",
            {"source": str(self.root / "source.mp4"), "source_sha256": "fake", "duration": 60},
        )
        common.save(self.p / "edit_plan.json", plan())

    def tearDown(self):
        gs.ROOT = self.old
        self.tmp.cleanup()

    def test_failed_qc_not_completed(self):
        bad = self.root / "bad.mp4"
        bad.write_bytes(b"broken")
        common.save(self.p / "qc_report.json", {"status": "failed", "output": str(bad)})
        self.assertFalse(gs.completed(self.p))

    def test_generic_hook_rejected(self):
        d = plan()
        d["clips"][0].update(caption="Watch this", narration="Something happens somewhere.")
        with self.assertRaises(ValueError):
            editorial.check_novelty(self.p, d)

    def test_history_repeated_hook_rejected(self):
        editorial.remember(self.p, "rejected", "Too repetitive")
        other = self.root / "other"
        with self.assertRaises(ValueError):
            editorial.check_novelty(other, plan())

    def test_rejected_hook_in_same_project_rejected(self):
        editorial.remember(self.p, "rejected", "Repeat")
        with self.assertRaises(ValueError):
            editorial.check_novelty(self.p, plan())

    def test_feedback_keeps_validated_range_reserved(self):
        editorial.remember(self.p, "validated")
        editorial.remember(self.p, "feedback", "Good pacing")
        other = self.root / "other"
        other.mkdir()
        common.save(other / "manifest.json", common.read(self.p / "manifest.json"))
        with self.assertRaises(ValueError):
            editorial.check_ranges(other, plan())

    def test_feedback_preserved(self):
        editorial.remember(self.p, "rejected", "No generic opening")
        editorial.remember(self.p, "planned")
        self.assertEqual(
            editorial.history(self.root / "other")[0]["feedback"], "No generic opening"
        )

    def test_voice_text_change_requests_new_audio(self):
        clips = plan()["clips"]
        for i in range(1, 6):
            tone(self.p / "Voices" / f"line_{i:02d}.wav")
        with patch.object(gs, "duration", return_value=1):
            old = voices.ensure(self.p, clips, adopt=True)
            self.assertEqual(old, voices.ensure(self.p, clips))
            clips[0]["narration"] = "A completely different story now."
            with patch.object(
                voices.bridge,
                "generate_voice_with_codex",
                side_effect=RuntimeError("new generation requested"),
            ) as gen:
                with self.assertRaisesRegex(RuntimeError, "new generation requested"):
                    voices.ensure(self.p, clips)
                gen.assert_called_once()
            self.assertTrue((old / "Voices/line_01.wav").exists())

    def test_voice_tampering_rejected(self):
        clips = plan()["clips"]
        for i in range(1, 6):
            tone(self.p / "Voices" / f"line_{i:02d}.wav")
        with patch.object(gs, "duration", return_value=1):
            folder = voices.ensure(self.p, clips, adopt=True)
            (folder / "Voices/line_01.wav").write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "changed or is missing"):
                voices.ensure(self.p, clips)

    def test_legacy_full_audio_not_automatically_regenerated(self):
        tone(self.p / "Audio/heygen_full.wav")
        with patch.object(voices.bridge, "generate_voice_with_codex") as gen:
            with self.assertRaisesRegex(RuntimeError, "no text provenance"):
                voices.ensure(self.p, plan()["clips"])
            gen.assert_not_called()

    def test_multiple_feedback_notes_retained(self):
        editorial.remember(self.p, "validated", "Good music")
        editorial.remember(self.p, "feedback", "Shorter opening")
        note = editorial.history(self.root / "other")[0]["feedback"]
        self.assertIn("Good music", note)
        self.assertIn("Shorter opening", note)

    def test_legacy_not_automatically_trusted(self):
        tone(self.p / "Voices/line_01.wav")
        with self.assertRaisesRegex(RuntimeError, "no text provenance"):
            voices.ensure(self.p, plan()["clips"])

    def test_legacy_changed_text_cannot_be_adopted(self):
        tone(self.p / "Voices/line_01.wav")
        common.save(self.p / "legacy_plan_snapshot.json", plan())
        d = plan()
        d["clips"][0]["narration"] = "New words"
        with self.assertRaisesRegex(RuntimeError, "Legacy text changed"):
            voices.ensure(self.p, d["clips"], adopt=True)

    def test_duration_change_reuses_voice_but_checks_fit(self):
        clips = plan()["clips"]
        for i in range(1, 6):
            tone(self.p / "Voices" / f"line_{i:02d}.wav")
        with patch.object(gs, "duration", return_value=1):
            voices.ensure(self.p, clips, adopt=True)
            clips[0]["duration"] = 0.5
            with self.assertRaisesRegex(RuntimeError, "does not fit"):
                voices.ensure(self.p, clips)

    def test_lock_rejects_second_process(self):
        path = self.root / "lock"
        with common.locked(path):
            code = (
                "from common import locked\nfrom pathlib import Path\nwith locked(Path("
                + repr(str(path))
                + ")): pass"
            )
            r = subprocess.run([sys.executable, "-c", code], cwd=common.HERE, capture_output=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(b"Another GamingShorts", r.stderr)

    def test_invalid_nan_plan_rejected(self):
        d = plan()
        d["clips"][0]["start"] = float("nan")
        common.save(self.p / "edit_plan.json", d)
        with self.assertRaises(ValueError):
            gs.validate(self.p)

    def test_overlap_rejected(self):
        editorial.remember(self.p, "validated")
        other = self.root / "other"
        other.mkdir()
        common.save(other / "manifest.json", common.read(self.p / "manifest.json"))
        with self.assertRaises(ValueError):
            editorial.check_ranges(other, plan())

    def test_nonoverlap_allowed(self):
        editorial.remember(self.p, "validated")
        other = self.root / "other"
        other.mkdir()
        common.save(other / "manifest.json", common.read(self.p / "manifest.json"))
        d = plan()
        for c in d["clips"]:
            c["start"] += 30
        editorial.check_ranges(other, d)

    def test_render_change_includes_audio_bytes(self):
        tone(self.p / "one.wav")
        a = gs.render_fingerprint(self.p, [self.p / "one.wav"])
        tone(self.p / "one.wav", 1.2)
        b = gs.render_fingerprint(self.p, [self.p / "one.wav"])
        self.assertNotEqual(a, b)

    def test_atomic_json(self):
        common.save(self.p / "x.json", {"ok": "✓"})
        self.assertEqual(common.read(self.p / "x.json"), {"ok": "✓"})
        self.assertEqual(list(self.p.glob("*.tmp")), [])

    def test_no_paid_api_or_delete_path(self):
        for name in ("start.py", "voices.py", "gaming_shorts.py"):
            s = (common.HERE / name).read_text()
            self.assertNotIn("api.heygen.com", s)
            self.assertNotIn("src.unlink()", s)


if __name__ == "__main__":
    unittest.main()
