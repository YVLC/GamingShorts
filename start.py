#!/usr/bin/env python3
"""Run the installed GamingShorts workflow from the workspace root."""

from pathlib import Path
import runpy
import sys


def main():
    runtime = Path(__file__).resolve().parent / "Automation" / "gamingshorts_v2"
    if not (runtime / "start.py").is_file():
        raise SystemExit(f"GamingShorts runtime missing: {runtime}")
    if sys.platform == "win32":
        raise SystemExit(
            "GamingShorts runs in Ubuntu/WSL. Open Ubuntu and run:\n"
            "  cd /mnt/d/GamingShorts\n  python3 start.py --help"
        )
    sys.path.insert(0, str(runtime))
    runpy.run_path(str(runtime / "start.py"), run_name="__main__")


if __name__ == "__main__":
    main()
