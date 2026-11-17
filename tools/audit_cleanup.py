#!/usr/bin/env python3
"""Audit failed split fragments for byte-identical copies and active references.

Writes a deletion plan only. Sources, successful outputs and original audio are
outside the candidate roots. Apply the plan with cleanup_workspace.ps1.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def normalized(value):
    return value.replace("\\", "/").lower().replace("/mnt/d/", "d:/")


def references(root):
    found = set()
    errors = []
    for folder in ("Projects", "Ready", "ReadyForReview", "Audio", "FootageIndex"):
        for path in (root / folder).rglob("*.json"):
            try:
                found.update(
                    normalized(value)
                    for value in strings(json.loads(path.read_text(encoding="utf-8-sig")))
                )
            except (OSError, ValueError) as error:
                errors.append(f"{path}: {error}")
    for path in (root / "Database").glob("*.sqlite3"):
        try:
            with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
                tables = [
                    row[0]
                    for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                ]
                for table in tables:
                    quoted = '"' + table.replace('"', '""') + '"'
                    for row in db.execute("SELECT * FROM " + quoted):
                        found.update(normalized(value) for value in row if isinstance(value, str))
        except (OSError, sqlite3.Error) as error:
            errors.append(f"{path}: {error}")
    return found, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    refs, errors = references(root)
    if errors:
        raise SystemExit(
            "Reference scan incomplete; refusing a deletion plan:\n" + "\n".join(errors)
        )
    by_size = defaultdict(list)
    for folder in ("_Processing", "SplitRetry"):
        for path in (root / folder).rglob("*.mp4"):
            if path.is_symlink() or not path.resolve().is_relative_to(root / folder):
                raise SystemExit(f"Unexpected symlink: {path}")
            relative = path.relative_to(root).as_posix()
            if any(
                normalized(str(path)) in value or normalized(relative) in value for value in refs
            ):
                continue
            by_size[path.stat().st_size].append(path)
    duplicates = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash = defaultdict(list)
        for path in sorted(paths):
            by_hash[checksum(path)].append(path)
        for digest, copies in by_hash.items():
            # Retain the first _Processing copy; no sources or final exports participate.
            copies.sort(key=lambda path: (path.parts[len(root.parts)] != "_Processing", str(path)))
            for redundant in copies[1:]:
                duplicates.append(
                    {
                        "delete": redundant.relative_to(root).as_posix(),
                        "keep": copies[0].relative_to(root).as_posix(),
                        "sha256": digest,
                        "bytes": size,
                    }
                )
    result = {
        "candidate_roots": ["_Processing", "SplitRetry"],
        "references_scanned": len(refs),
        "duplicates": duplicates,
        "reclaim_bytes": sum(item["bytes"] for item in duplicates),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"Verified {len(duplicates)} unused duplicate fragments; {result['reclaim_bytes'] / 1024**3:.3f} GiB reclaimable"
    )


if __name__ == "__main__":
    main()
