"""Explicit cache lifetimes for completed reads and newly owned exports."""

import os

from compact_storage import encoded_blocks
from lifetime_io import WINDOW
from paged_io import THRESHOLD


REQUESTS = []


def release_read(path, stage):
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if size < THRESHOLD:
            return
        os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    REQUESTS.append({"stage": stage, "path": str(path), "bytes": size, "kind": "completed-read", "synced": False})


def release_output(path, stage):
    # Only newly owned output files are opened writable or synchronized.
    with path.open("r+b") as stream:
        size = os.fstat(stream.fileno()).st_size
        if size < THRESHOLD:
            return
        os.fdatasync(stream.fileno())
        os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
    REQUESTS.append({"stage": stage, "path": str(path), "bytes": size, "kind": "completed-output", "synced": True})


def write_blocks(path, blocks):
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix(path.suffix + ".part")
    advised, pending, syncs = 0, 0, 0
    with temporary.open("xb") as stream:
        for block in blocks:
            # Bound the pending range even if a single canonical row is very large.
            remaining = memoryview(block)
            while remaining:
                size = min(len(remaining), WINDOW - pending)
                piece, remaining = remaining[:size], remaining[size:]
                stream.write(piece)
                pending += len(piece)
                if pending >= WINDOW:
                    stream.flush(); os.fdatasync(stream.fileno())
                    os.posix_fadvise(stream.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
                    advised += pending; pending = 0; syncs += 1
        stream.flush(); os.fdatasync(stream.fileno())
        if pending:
            os.posix_fadvise(stream.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
            advised += pending; syncs += 1
        os.fsync(stream.fileno())
    # Publish a completed file without replacing an existing destination.
    os.link(temporary, path)
    temporary.unlink()
    record = {"path": str(path), "bytes": advised, "syncs": syncs, "windowBytes": WINDOW, "kind": "streamed-output"}
    REQUESTS.append(record)
    return record


def save_json(path, value):
    return write_blocks(path, encoded_blocks(value))


def report():
    return {"requests": list(REQUESTS), "windowBytes": WINDOW, "readThresholdBytes": THRESHOLD,
            "scope": "Per-file advice after successful completed reads; fdatasync only on newly owned outputs, including bounded completed export ranges. Kernel advice is not guaranteed eviction; no source-byte edits or global cache drop."}
