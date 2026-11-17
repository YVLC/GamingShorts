"""Safe regression tests for long-recording reuse and source inspection."""

import json, shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

import common, start, shared_index, editorial, gaming_shorts as gs


class MultiClipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original = gs.ROOT
        gs.ROOT = self.root
        (self.root / "Sources").mkdir()
        self.source = self.root / "Sources" / "example.mp4"
        self.source.write_bytes(b"static-fixture-data" * 100)

    def tearDown(self):
        gs.ROOT = self.original
        self.tmp.cleanup()

    def test_reuse_source_checksum_across_variants(self):
        with patch.object(gs, "duration", return_value=5400):
            a = start.prepare(self.source, "one")
            with patch.object(
                start, "digest", side_effect=AssertionError("duplicate full-source checksum")
            ):
                b = start.prepare(self.source, "two")
                self.assertEqual(
                    common.read(a / "manifest.json")["source_sha256"],
                    common.read(b / "manifest.json")["source_sha256"],
                )
                self.assertNotEqual(a, b)
                self.assertEqual(a, start.prepare(self.source, "one"))

    def test_cached_surveys_reused_across_variants(self):
        sha = common.digest(self.source)
        data = {
            "source": str(self.source),
            "source_sha256": sha,
            "source_size_bytes": self.source.stat().st_size,
            "source_modified_ns": self.source.stat().st_mtime_ns,
            "duration": 5400,
        }
        a = self.root / "one"
        b = self.root / "two"
        a.mkdir()
        b.mkdir()
        common.save(a / "manifest.json", data)
        common.save(b / "manifest.json", data)
        made = []

        def fake_sheet(source, at, span, dest, label):
            dest.write_bytes(b"JPEG-fixture" + bytes(str(at), "utf8") + b"0" * 1024)
            made.append(dest)

        with patch.object(editorial, "sheet", side_effect=fake_sheet):
            first = shared_index.surveys(a)
            second = shared_index.surveys(b)
        self.assertEqual(len(made), 8)
        self.assertEqual(first, second)

    def test_changed_source_blocks_cached_images(self):
        data = {
            "source": str(self.source),
            "source_sha256": "placeholder",
            "source_size_bytes": self.source.stat().st_size + 1,
            "source_modified_ns": self.source.stat().st_mtime_ns,
            "duration": 5400,
        }
        p = self.root / "project"
        p.mkdir()
        common.save(p / "manifest.json", data)
        with self.assertRaisesRegex(RuntimeError, "changed size"):
            shared_index.surveys(p)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg unavailable")
    def test_later_preview_region_renders(self):
        import subprocess

        self.source.unlink()
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x180:rate=15",
                "-t",
                "22",
                "-c:v",
                "mpeg4",
                str(self.source),
            ],
            check=True,
        )
        out = self.root / "Sheets" / "later.jpg"
        out.parent.mkdir()
        editorial.sheet(self.source, 15, 5, out, "survey")
        self.assertGreater(out.stat().st_size, 800)


if __name__ == "__main__":
    unittest.main()
