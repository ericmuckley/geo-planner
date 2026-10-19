"""Versioned per-file cache advice after large, completed checksum reads."""

import hashlib
import os


THRESHOLD = 8 * 1024 ** 2
REQUESTS = []


def file_hash(path, advise=True):
    with path.open("rb") as stream:
        result = hashlib.file_digest(stream, "sha256").hexdigest()
        size = os.fstat(stream.fileno()).st_size
        if advise and size >= THRESHOLD:
            if not hasattr(os, "posix_fadvise"): raise RuntimeError("This recipe requires Linux posix_fadvise")
            os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            REQUESTS.append({"path": str(path), "bytes": size})
        return result


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def advice_report():
    return {"policy": "POSIX_FADV_DONTNEED after checksum reads of files >= 8 MiB", "requests": list(REQUESTS),
            "scope": "Per-file advisory request after completed reads; no file edits or global cache drop. The kernel may retain pages; measured cgroup composition establishes the observed effect."}
