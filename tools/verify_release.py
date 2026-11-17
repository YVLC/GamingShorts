#!/usr/bin/env python3
"""Verify source/retirement ZIPs and the retained copies behind cleanup deletions."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    release = args.release.resolve()
    results = {}
    for manifest_name, archive_name in (
        ("SHA256SUMS.json", "GamingShorts-automation-2026-11-12.zip"),
        ("retired-manifest.json", "retired-tools.zip"),
    ):
        manifest = json.loads((release / manifest_name).read_text(encoding="utf-8-sig"))
        with ZipFile(release / archive_name) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {item["path"] for item in manifest}
            for item in manifest:
                assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"], (
                    item["path"]
                )
        results[archive_name] = {"files": len(manifest), "sha256": checksum(release / archive_name)}
    deleted = json.loads((release / "removed-duplicates.json").read_text(encoding="utf-8-sig"))
    checked = {}
    for item in deleted:
        retained = (root / item["keep"]).resolve()
        removed = (root / item["delete"]).resolve()
        assert retained.is_relative_to(root) and removed.is_relative_to(root)
        assert not removed.exists(), removed
        if retained not in checked:
            checked[retained] = checksum(retained)
        assert checked[retained] == item["sha256"], retained
    results["cleanup"] = {
        "deleted_duplicates": len(deleted),
        "retained_distinct_copies": len(checked),
        "reclaimed_bytes": sum(item["bytes"] for item in deleted),
    }
    for name in ("captions.py", "config.json", "preferences.json"):
        assert (release / "before" / name).read_bytes() == (
            root / "Automation/gamingshorts_v2" / name
        ).read_bytes(), name
    results["byte_identical_to_baseline"] = ["captions.py", "config.json", "preferences.json"]
    (release / "verification.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
