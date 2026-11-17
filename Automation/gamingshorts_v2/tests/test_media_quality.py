"""Cadence, proxy roles, safe boundaries, caption cache keys and native geometry."""

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

import common
import gaming_shorts as gs
import audio_pipeline as audio
import quality_checks as quality
import render_sources


class CadenceTests(unittest.TestCase):
    def moving(self, frames=120):
        x = np.arange(96)[None, :]
        y = np.arange(54)[:, None]
        return np.array([((x + frame * 2 + y * 0.2) % 64) * 3 for frame in range(frames)], np.uint8)

    def test_15_updates_labeled_60_are_detected(self):
        original = self.moving()
        duplicated = np.repeat(original[::4], 4, axis=0)
        before = quality.cadence_from_frames(original, 60)
        after = quality.cadence_from_frames(duplicated, 60)
        self.assertEqual(quality.compare_cadence(before, after)["status"], "failed")
        self.assertGreater(after["near_duplicate_fraction"], 0.70)

    def test_genuinely_static_footage_is_not_failed(self):
        static = np.zeros((120, 54, 96), np.uint8)
        report = quality.cadence_from_frames(static, 60)
        self.assertEqual(report["status"], "static_or_low_motion")
        self.assertIsNone(quality.compare_cadence(report, report)["error"])

    def test_static_noise_is_not_claimed_as_sustained_motion(self):
        static = 100 + np.random.default_rng(7).normal(0, 0.03, (120, 54, 96))
        self.assertEqual(quality.cadence_from_frames(static, 60)["active_windows"], 0)

    def test_native_15fps_is_not_promoted_to_60(self):
        self.assertEqual(render_sources.delivery_rate([{"fps": Fraction(15)}], 60), 15)
        profile = quality.cadence_from_frames(self.moving(30), 15)
        self.assertFalse(profile["cadence_limited"])

    def test_fractional_source_cadence_is_preserved(self):
        self.assertEqual(
            render_sources.delivery_rate([{"fps": Fraction(60000, 1001)}], 60),
            Fraction(60000, 1001),
        )

    def test_proxy_role_cannot_be_rendered_or_queued(self):
        with self.assertRaisesRegex(ValueError, "Inspection proxy"):
            quality.production_source("/recordings/ReviewCopies/source.mp4")

    def test_low_resolution_uses_sharp_contain_instead_of_huge_crop(self):
        graph, report = render_sources.picture_filters(
            {"width": 1280, "height": 676}, {"width": 1080, "height": 1920}
        )
        self.assertEqual(report["mode"], "blur_contain")
        self.assertIn("[sharp]", graph)
        with self.assertRaisesRegex(ValueError, "enlarge"):
            render_sources.picture_filters(
                {"width": 1280, "height": 676}, {"width": 1080, "height": 1920}, "cover"
            )

    def test_native_4k_portrait_crop_does_not_enlarge(self):
        _, report = render_sources.picture_filters(
            {"width": 3840, "height": 2026}, {"width": 1080, "height": 1920}
        )
        self.assertEqual(report["mode"], "cover")
        self.assertLess(report["cover_enlargement"], 1)


class BoundaryTests(unittest.TestCase):
    def test_trailing_ts_stays_with_its_word(self):
        rate = 48000
        t = np.arange(rate * 2) / rate
        raw = np.zeros(rate * 2, dtype=np.float32)
        raw[rate // 10 : round(0.85 * rate)] = 0.12 * np.sin(
            2 * np.pi * 230 * t[rate // 10 : round(0.85 * rate)]
        )
        lo, hi = round(0.85 * rate), round(1.33 * rate)
        raw[lo:hi] = 0.12 * np.sin(2 * np.pi * 8000 * t[lo:hi])
        raw[round(1.5 * rate) :] = 0.1 * np.sin(2 * np.pi * 300 * t[round(1.5 * rate) :])
        original = raw.copy()
        cuts, checks = audio.safe_boundaries(raw, [(0.1, 0.9), (1.5, 1.9)])
        self.assertGreater(cuts[1], 1.33)
        self.assertLess(cuts[1], 1.48)
        self.assertGreater(checks[0]["old_boundary_dbfs"], -30)
        self.assertLess(checks[0]["new_boundary_dbfs"], -50)
        first = audio.quiet_edge_fade(raw[: round(cuts[1] * rate)])
        self.assertTrue(np.array_equal(first[lo:hi], original[lo:hi]))
        self.assertTrue(np.array_equal(raw, original))

    def test_already_quiet_midpoints_stay_unchanged(self):
        raw = np.zeros(48000 * 2, np.float32)
        cuts, checks = audio.safe_boundaries(raw, [(0.1, 0.8), (1.2, 1.8)])
        self.assertEqual(cuts[1], 1.0)
        self.assertFalse(checks[0]["moved"])

    def test_no_safe_gap_stops_instead_of_erasing_speech(self):
        raw = np.ones(48000 * 2, np.float32) * 0.1
        with self.assertRaisesRegex(RuntimeError, "No safe quiet boundary"):
            audio.safe_boundaries(raw, [(0.1, 0.9), (1.5, 1.9)])

    def test_fades_never_modify_audible_consonants(self):
        raw = np.ones(4800, np.float32) * 0.1
        self.assertTrue(np.array_equal(audio.quiet_edge_fade(raw), raw))

    def test_fades_only_touch_tiny_quiet_edge_handles(self):
        raw = np.ones(4800, np.float32) * 0.0001
        result = audio.quiet_edge_fade(raw)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[-1], 0)
        self.assertTrue(np.array_equal(result[96:-96], raw[96:-96]))

    def test_linear_gain_preserves_high_frequency_consonant_energy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rate = 48000
            t = np.arange(rate) / rate
            signal = (
                0.05 * np.sin(2 * np.pi * 240 * t) + 0.03 * np.sin(2 * np.pi * 8000 * t)
            ).astype(np.float32)
            source = root / "voice.wav"
            target = root / "normal.wav"
            audio.export_segment(signal, source)
            gs.normalize_voice_exact(source, target, 1, common.config(), gain_db=3)
            original = audio.read_audio(source)
            output = audio.read_audio(target)
            self.assertEqual(len(output), rate)
            self.assertAlmostEqual(audio.level(output) - audio.level(original), 3, places=2)
            self.assertGreater(float(np.corrcoef(original, output)[0, 1]), 0.99999)


class VisualCacheTests(unittest.TestCase):
    def test_cache_rejects_duplicate_frame_poison_and_binds_caption_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            out = p / "render"
            out.mkdir()
            source = p / "original.mp4"
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
                    "testsrc2=size=320x180:rate=60",
                    "-t",
                    "2",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    source,
                ]
            )
            cfg = dict(
                common.DEFAULTS, width=144, height=256, fps=60, crf=24, x264_preset="ultrafast"
            )
            resolved = {
                "path": source,
                "sha256": common.digest(source),
                "start": 0.0,
                "duration": 2.0,
                "width": 320,
                "height": 180,
                "fps": Fraction(60),
                "timeline_start": 0.0,
            }
            graph, framing = render_sources.picture_filters(resolved, cfg, "blur_contain")
            text = out / "caption_1_0.txt"
            text.write_text("Original caption")
            graph += f",drawtext=fontfile={cfg['font']}:textfile=caption_1_0.txt:y=h*0.8"
            _, first = render_sources.encode_shot(
                p,
                out,
                1,
                resolved,
                cfg,
                graph,
                Fraction(60),
                framing,
                common.run,
                gs.probe,
                gs.duration,
            )
            self.assertFalse(first["reused"])
            cache = next((p / "VideoCache").iterdir())
            poisoned = p / "poisoned.mp4"
            common.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-y",
                    "-i",
                    out / "shot_01.mp4",
                    "-vf",
                    "fps=15,fps=60",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    poisoned,
                ]
            )
            import shutil

            shutil.copyfile(poisoned, cache / "shot.mp4")
            proof = common.read(cache / "proof.json")
            proof["sha256"] = common.digest(cache / "shot.mp4")
            common.save(cache / "proof.json", proof)
            _, repaired = render_sources.encode_shot(
                p,
                out,
                1,
                resolved,
                cfg,
                graph,
                Fraction(60),
                framing,
                common.run,
                gs.probe,
                gs.duration,
            )
            self.assertFalse(repaired["reused"])
            self.assertEqual(repaired["cadence_comparison"]["status"], "pass")
            text.write_text("A changed caption")
            render_sources.encode_shot(
                p,
                out,
                1,
                resolved,
                cfg,
                graph,
                Fraction(60),
                framing,
                common.run,
                gs.probe,
                gs.duration,
            )
            self.assertEqual(len(list((p / "VideoCache").iterdir())), 2)
