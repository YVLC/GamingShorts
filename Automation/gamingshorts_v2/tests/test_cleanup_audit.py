"""A cleanup plan must exclude referenced fragments and every protected folder."""

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


class CleanupAuditTests(unittest.TestCase):
    def test_only_unreferenced_identical_failed_fragments_are_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("_Processing", "SplitRetry", "Sources", "ReadyForReview", "Projects"):
                (root / folder).mkdir()
            for folder in ("_Processing", "SplitRetry", "Sources", "ReadyForReview"):
                (root / folder / "same.mp4").write_bytes(b"identical fixture")
                (root / folder / "referenced.mp4").write_bytes(b"protected fixture")
            (root / "_Processing/different.mp4").write_bytes(b"aaaa")
            (root / "SplitRetry/different.mp4").write_bytes(b"bbbb")
            (root / "Projects/reference.json").write_text(
                json.dumps({"source": str(root / "SplitRetry/referenced.mp4")})
            )
            output = root / "plan.json"
            tool = Path(__file__).resolve().parents[3] / "tools/audit_cleanup.py"
            subprocess.run(
                [sys.executable, str(tool), "--root", str(root), "--output", str(output)],
                check=True,
            )
            plan = json.loads(output.read_text())
            self.assertEqual(
                [item["delete"] for item in plan["duplicates"]], ["SplitRetry/same.mp4"]
            )
            self.assertEqual(plan["duplicates"][0]["keep"], "_Processing/same.mp4")
            self.assertTrue((root / "SplitRetry/same.mp4").is_file(), "Audit must never delete")

    def test_incomplete_reference_scan_refuses_a_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Projects").mkdir()
            (root / "Projects/broken.json").write_text("not JSON")
            tool = Path(__file__).resolve().parents[3] / "tools/audit_cleanup.py"
            output = root / "plan.json"
            result = subprocess.run(
                [sys.executable, str(tool), "--root", str(root), "--output", str(output)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
