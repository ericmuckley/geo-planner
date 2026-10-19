"""Stream native output with bounded dirty ranges and per-file cache advice."""

import os
import subprocess
import time


WINDOW = 16 * 1024 ** 2


def copy_advised(source, destination):
    advised, pending, syncs = 0, 0, 0
    with destination.open("xb") as target:
        while block := source.read(1024 * 1024):
            target.write(block)
            pending += len(block)
            if pending >= WINDOW:
                target.flush(); os.fdatasync(target.fileno())
                os.posix_fadvise(target.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
                advised += pending; pending = 0; syncs += 1
        if pending:
            target.flush(); os.fdatasync(target.fileno())
            os.posix_fadvise(target.fileno(), advised, pending, os.POSIX_FADV_DONTNEED)
            advised += pending; syncs += 1
    return {"bytes": advised, "syncs": syncs, "windowBytes": WINDOW,
            "policy": "fdatasync and POSIX_FADV_DONTNEED for completed output ranges only; no global cache drop"}


def stream_command(args, destination, output, stage, monitor=None):
    before = time.perf_counter()
    with (output / f"{stage}.log").open("wb") as log:
        child = subprocess.Popen(["/usr/bin/time", "-v", "-o", str(output / f"{stage}-resources.txt"), *args], stdout=subprocess.PIPE, stderr=log)
        try:
            advice = copy_advised(child.stdout, destination)
            child.stdout.close()
            status = child.wait()
            if status: raise subprocess.CalledProcessError(status, args)
        except BaseException:
            child.terminate(); child.wait()
            if child.stdout: child.stdout.close()
            raise
    if monitor: monitor.checkpoint(stage)
    return {"command": args, "wallMs": (time.perf_counter() - before) * 1000, "outputAdvice": advice}


def partition_ids(source, output, batches):
    if batches not in (1, 4): raise ValueError("Use one or four fixed reference batches")
    with source.open() as lines:
        count = sum(1 for _ in lines)
    size = max(1, (count + batches - 1) // batches)
    parts, stream = [], None
    try:
        with source.open() as lines:
            for index, line in enumerate(lines):
                if index % size == 0:
                    if stream: stream.close()
                    path = output / f"reference-ids-{len(parts)}.txt"
                    stream = path.open("x"); parts.append(path)
                stream.write(line)
    finally:
        if stream: stream.close()
    if not parts:
        path = output / "reference-ids-0.txt";path.touch(exist_ok=False);parts.append(path)
    return parts
