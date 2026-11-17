"""Environment diagnostics must use FFmpeg's filter list, not Codex output."""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import start


class DoctorTests(unittest.TestCase):
    def check_doctor(self, has_ass):
        filters = "drawtext loudnorm alimiter blackdetect freezedetect\n"
        if has_ass:
            filters += " ... ass V->V Render subtitles\n"

        def execute(command, **kwargs):
            if command[-1] == "-filters":
                return CompletedProcess(command, 0, filters, "")
            if command[-1] == "filter=alimiter":
                return CompletedProcess(command, 0, "latency", "")
            if command[1:3] == ["exec", "--help"]:
                return CompletedProcess(
                    command, 0, "--output-schema --image --ephemeral --sandbox", ""
                )
            return CompletedProcess(command, 0, "logged in", "")

        with (
            patch.object(
                start, "config", return_value={"font": __file__, "caption_mode": "karaoke"}
            ),
            patch.object(start.shutil, "which", side_effect=lambda name: "/usr/bin/" + name),
            patch.object(start.subprocess, "run", side_effect=execute) as run,
            redirect_stdout(io.StringIO()),
        ):
            if has_ass:
                start.doctor()
            else:
                with self.assertRaisesRegex(RuntimeError, "libass"):
                    start.doctor()
            self.assertEqual(sum(call.args[0][-1] == "-filters" for call in run.call_args_list), 1)

    def test_karaoke_filters_checked_once(self):
        self.check_doctor(True)

    def test_missing_libass_reported(self):
        self.check_doctor(False)
