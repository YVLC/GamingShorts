"""Offline coverage for retained speech timings and uncertain-call protection."""

from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import captions
import common
import voice_bridge as bridge
from test_regressions import tone


class VoiceHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.audio = self.folder / "full.wav"
        tone(self.audio, 4)
        import wave
        import array

        with wave.open(str(self.audio), "rb") as reader:
            parameters = reader.getparams()
            samples = array.array("h", reader.readframes(reader.getnframes()))
        samples[round(0.95 * 16000) : round(2.15 * 16000)] = array.array(
            "h", [0] * round(1.2 * 16000)
        )
        with wave.open(str(self.audio), "wb") as writer:
            writer.setparams(parameters)
            writer.writeframes(samples.tobytes())
        self.clips = [
            {"narration": "Hello there.", "duration": 3},
            {"narration": "Subscribe now.", "duration": 3},
        ]
        self.result = {
            "voice_id": common.config()["voice_id"],
            "model": "heygen-voice-1-turbo-free",
            "duration_seconds": 4,
            "phrases": [
                {"index": 1, "first_word_start": 0.2, "last_word_end": 0.9},
                {"index": 2, "first_word_start": 2.2, "last_word_end": 2.9},
            ],
            "words": [
                {"word": "Hello", "start": 0.2, "end": 0.5},
                {"word": "there", "start": 0.6, "end": 0.9},
                {"word": "Subscribe", "start": 2.2, "end": 2.5},
                {"word": "now", "start": 2.6, "end": 2.9},
            ],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_saved_words_survive_real_audio_split_and_align_locally(self):
        bridge.split_speech(self.folder, self.clips, self.result["phrases"], self.audio)
        self.assertTrue(
            bridge.save_word_timestamps(self.folder, self.clips, self.result, self.audio)
        )
        saved = common.read(self.folder / "heygen_word_timestamps.json")
        self.assertEqual(saved["audio_sha256"], common.digest(self.audio))
        aligned = captions._from_saved_heygen_words(self.folder, self.clips)
        self.assertEqual(len(aligned["lines"]), 2)
        self.assertAlmostEqual(aligned["lines"][1]["words"][0]["start"], 0.65)
        self.assertEqual(captions.load(self.folder, self.clips), aligned)

    def test_bad_words_do_not_produce_a_sidecar(self):
        for mutation in ("wrong_text", "out_of_audio", "phrase_mismatch", "wrong_voice"):
            result = deepcopy(self.result)
            if mutation == "wrong_text":
                result["words"][0]["word"] = "Goodbye"
            elif mutation == "out_of_audio":
                result["words"][-1]["end"] = 5
            elif mutation == "phrase_mismatch":
                result["phrases"][0]["first_word_start"] = 0
            else:
                result["voice_id"] = "unapproved"
            with (
                self.subTest(mutation=mutation),
                self.assertRaises((ValueError, bridge.WorkflowError)),
            ):
                bridge.save_word_timestamps(self.folder, self.clips, result, self.audio)
            self.assertFalse((self.folder / "heygen_word_timestamps.json").exists())

    def test_conflicting_saved_words_are_preserved(self):
        path = self.folder / "heygen_word_timestamps.json"
        common.save(path, {"script": ["previous result"]})
        before = path.read_bytes()
        with self.assertRaisesRegex(bridge.WorkflowError, "conflicts"):
            bridge.save_word_timestamps(self.folder, self.clips, self.result, self.audio)
        self.assertEqual(path.read_bytes(), before)

    def test_legacy_result_without_words_never_invents_them(self):
        self.assertFalse(bridge.save_word_timestamps(self.folder, self.clips, {}, self.audio))
        self.assertFalse((self.folder / "heygen_word_timestamps.json").exists())

    def test_schema_requires_actual_word_timing_payload(self):
        path = self.folder / "schema.json"
        bridge.voice_schema(path, 2)
        schema = common.read(path)
        self.assertIn("words", schema["required"])
        self.assertEqual(
            schema["properties"]["words"]["items"]["required"], ["word", "start", "end"]
        )

    def test_uncertain_speech_timeout_is_never_automatically_retried(self):
        with (
            patch.object(bridge.shutil, "which", return_value="codex"),
            patch.object(
                bridge.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 1)
            ) as run,
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                bridge.generate_voice_with_codex(self.folder, self.clips, False)
            marker = self.folder / "voice_generation_attempted.json"
            self.assertTrue(marker.exists())
            with self.assertRaisesRegex(bridge.WorkflowError, "automatic retries are blocked"):
                bridge.generate_voice_with_codex(self.folder, self.clips, False)
            self.assertEqual(run.call_count, 1)
