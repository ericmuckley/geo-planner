"""Identical SHA-256 with advice on bounded, completed checksum-read ranges."""

import hashlib
import os

from lifetime_io import WINDOW
from paged_io import THRESHOLD


REQUESTS = []


def file_hash(path, advise=True):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        enabled = advise and size >= THRESHOLD
        advised, pending, ranges = 0, 0, 0
        while block := stream.read(min(1024**2, WINDOW - pending)):
            result.update(block)
            pending += len(block)
            if pending == WINDOW:
                if enabled:
                    os.posix_fadvise(stream.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
                advised += pending; pending = 0; ranges += 1
        if pending:
            if enabled:
                os.posix_fadvise(stream.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
            advised += pending; ranges += 1
        if enabled:
            REQUESTS.append({"path": str(path), "bytes": advised, "ranges": ranges, "windowBytes": WINDOW})
    return result.hexdigest()


def artifact(path):
    return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def advice_report():
    return {"policy": "POSIX_FADV_DONTNEED on completed checksum-read ranges <= 16 MiB for files >= 8 MiB", "requests": list(REQUESTS),
            "scope": "Read-only original bytes and identical SHA-256. Advice is not guaranteed eviction; no source synchronization, edits or global cache drop."}
