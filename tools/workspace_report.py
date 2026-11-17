#!/usr/bin/env python3
"""Print a read-only workspace inventory without following directory symlinks."""

import argparse
import json
import os
from pathlib import Path

EXCLUDED = {".tools", ".git", "__pycache__", ".ruff_cache", ".venv"}


def inventory(root):
    rows = []
    errors = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not folder.is_dir() or folder.is_symlink() or folder.name in EXCLUDED:
            continue
        count = size = 0

        def onerror(error):
            errors.append(str(error))

        for parent, directories, files in os.walk(folder, onerror=onerror):
            directories[:] = sorted(
                name
                for name in directories
                if name not in EXCLUDED and not (Path(parent) / name).is_symlink()
            )
            for name in files:
                path = Path(parent) / name
                try:
                    if path.is_symlink():
                        continue
                    size += path.stat().st_size
                    count += 1
                except OSError as error:
                    errors.append(str(error))
        rows.append({"folder": folder.name, "files": count, "bytes": size})
    return {"root": str(root), "folders": rows, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    report = inventory(args.root.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Workspace: {report['root']}\n{'Folder':36} {'Files':>8} {'GiB':>10}")
        for row in report["folders"]:
            print(f"{row['folder']:36} {row['files']:8} {row['bytes'] / 1024**3:10.3f}")
        for error in report["errors"]:
            print(f"Scan error: {error}")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
