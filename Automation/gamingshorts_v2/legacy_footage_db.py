"""Read-only compatibility fingerprint for V1 footage records."""

import hashlib
from pathlib import Path


def fingerprint(path: Path) -> str:
    """Fast *sampled* content ID: size + first and last 4 MiB.

    Works for identical reuploads/renamed source clips but is not a full-file cryptographic hash.
    """
    size = path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode("ascii"))
    n = 4 * 1024 * 1024
    with path.open("rb") as f:
        h.update(f.read(n))
        if size > n:
            f.seek(max(0, size - n))
            h.update(f.read(n))
    return "sampled-sha256:" + h.hexdigest()
