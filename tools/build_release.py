#!/usr/bin/env python3
"""Package a complete reviewable source snapshot and verify its ZIP checksums."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--archive-name", default="GamingShorts-automation-2026-11-12.zip")
    args = parser.parse_args()
    if Path(args.archive_name).name != args.archive_name or not args.archive_name.endswith(".zip"):
        parser.error("--archive-name must be a ZIP filename without directories")
    root = Path(__file__).resolve().parents[1]
    release = args.release.resolve()
    if not release.is_relative_to(root / "Releases"):
        raise SystemExit("Release must be inside the workspace Releases folder")
    snapshot = release / "after"
    snapshot.mkdir(parents=True, exist_ok=False)
    files = []
    excluded = {"__pycache__", ".align-venv", ".ruff_cache", "Backups"}
    runtime = root / "Automation/gamingshorts_v2"
    for path in runtime.rglob("*"):
        relative = path.relative_to(runtime)
        if path.is_file() and not path.is_symlink() and not set(relative.parts) & excluded:
            if (
                path.suffix in {".py", ".json", ".md", ".sh", ".service"}
                or (path.name.startswith('requirements') and path.suffix=='.txt')
                or relative.parts[0] == "music"
            ):
                files.append(path)
    for name in ("docs", "tools"):
        files.extend(
            path
            for path in (root / name).rglob("*")
            if path.is_file() and not path.is_symlink() and not set(path.parts) & excluded
        )
    files.extend(
        root / name
        for name in (
            "README.md",
            "start.py",
            "pyproject.toml",
            ".gitignore",
            "export_cairn_previews.py",
            "Cairn_90min_Review_Manifest.json",
            "Cairn_90min_Shortlist.md",
            "Cairn_90min_Storyboard.jpg",
        )
    )
    manifest = []
    for source in sorted(set(files)):
        relative = source.relative_to(root)
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = checksum(target)
        if checksum(source) != digest:
            raise RuntimeError(f"Source changed while packaging: {source}")
        manifest.append(
            {"path": relative.as_posix(), "sha256": digest, "bytes": target.stat().st_size}
        )
    (release / "SHA256SUMS.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    bundle = release / args.archive_name
    with ZipFile(bundle, "x", ZIP_DEFLATED) as archive:
        for item in manifest:
            archive.write(snapshot / item["path"], item["path"])
    with ZipFile(bundle) as archive:
        assert archive.testzip() is None
        for item in manifest:
            assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"], item[
                "path"
            ]
    print(f"Verified complete release: {len(manifest)} files | {bundle}")


if __name__ == "__main__":
    main()
