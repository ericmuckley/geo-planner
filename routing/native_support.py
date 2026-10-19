"""Packed-graph I/O, reproducible compiler invocation and bounded local IPC."""

import json
import math
import os
from pathlib import Path
import select
import shutil
import struct
import subprocess
import time

from anchors import file_hash
from state_graph import nonnegative_integer


UINT32_MAX = (1 << 32) - 1
UINT64_MAX = (1 << 64) - 1


def pack_graph(adjacency, identity):
    if not 0 < len(adjacency) <= UINT32_MAX or len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("Invalid graph size/identity")
    graph_id = bytes.fromhex(identity)
    offsets, targets, weights = [0], [], []
    for row in adjacency:
        for target, cost in row:
            if not isinstance(target, int) or isinstance(target, bool) or not 0 <= target < len(adjacency):
                raise ValueError("Invalid arc target")
            nonnegative_integer(cost)
            if cost > UINT32_MAX:
                raise ValueError("Arc cost exceeds uint32")
            targets.append(target)
            weights.append(cost)
        offsets.append(len(targets))
    if len(targets) > UINT32_MAX:
        raise ValueError("Arc count exceeds uint32")
    return (struct.pack("<8sII32s", b"GPCSR001", len(adjacency), len(targets), graph_id)
            + b"".join(struct.pack(f"<{len(values)}I", *values) for values in (offsets, targets, weights)))


def verify_packed(path, expected):
    if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]:
        raise ValueError("Packed graph checksum mismatch")


def compiler_config():
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        raise RuntimeError("A C++17 compiler is required (Clang or GCC); see docs/native-routing-baseline.md")
    flags = ["-std=c++17", "-O3", "-Wall", "-Wextra", "-Werror"]
    version = subprocess.check_output([compiler, "--version"], text=True)
    return {"compiler": compiler, "version": version, "flags": flags}


def compile_kernel(output, config=None):
    config = config or compiler_config()
    source = Path(__file__).with_name("native_search.cpp")
    before = time.perf_counter()
    try:
        subprocess.run([config["compiler"], *config["flags"], str(source), "-o", str(output)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Native compilation failed: {error.stderr}") from error
    return {**config,
            "compileMs": (time.perf_counter() - before) * 1000, "sourceSha256": file_hash(source),
            "binarySha256": file_hash(output), "binaryBytes": output.stat().st_size}


class NativeClient:
    def __init__(self, binary, graph_path, identity, timeout=30):
        self.timeout, self.buffer, self.sequence = timeout, bytearray(), 0
        before = time.perf_counter()
        self.process = subprocess.Popen([str(binary), str(graph_path), identity], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.hello = json.loads(self.line(time.monotonic() + timeout))
            if self.hello.get("program") != "csr-dijkstra-v1":
                raise ValueError("Unexpected native protocol")
            self.startup_ms = (time.perf_counter() - before) * 1000
        except Exception:
            self.close()
            raise

    def receive(self, deadline):
        ready, _, _ = select.select([self.process.stdout], [], [], max(0, deadline - time.monotonic()))
        if not ready:
            raise TimeoutError("Native response timed out")
        chunk = os.read(self.process.stdout.fileno(), 65536)
        if not chunk:
            self.process.wait(timeout=2)
            raise RuntimeError(self.process.stderr.read().decode().strip() or "Native process closed output")
        self.buffer.extend(chunk)

    def line(self, deadline):
        while b"\n" not in self.buffer:
            if len(self.buffer) > 4096:
                raise ValueError("Native metadata line too large")
            self.receive(deadline)
        index = self.buffer.index(b"\n")
        result = bytes(self.buffer[:index])
        del self.buffer[:index + 1]
        return result

    def request(self, seeds, budget, mode="labels"):
        self.sequence += 1
        fields = [str(self.sequence), "full" if budget is None else str(budget), mode, str(len(seeds))]
        fields.extend(str(value) for seed in seeds for value in seed)
        before = time.perf_counter()
        self.process.stdin.write((" ".join(fields) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + self.timeout
        metadata = json.loads(self.line(deadline))
        expected_bytes = self.hello["states"] * 8 if mode == "labels" else (self.hello["states"] + 7) // 8
        if metadata.get("requestId") != self.sequence or metadata.get("mode") != mode or metadata.get("payloadBytes") != expected_bytes:
            raise ValueError("Native response identity/size mismatch")
        if metadata.get("complete") != (budget is None) or metadata.get("budgetMs") != budget:
            raise ValueError("Native response budget/horizon mismatch")
        while len(self.buffer) < expected_bytes:
            self.receive(deadline)
        payload = bytes(self.buffer[:expected_bytes])
        del self.buffer[:expected_bytes]
        return metadata, payload, (time.perf_counter() - before) * 1000

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        for stream in (self.process.stdout, self.process.stderr):
            if stream: stream.close()


def decode_labels(payload, count):
    if len(payload) != count * 8:
        raise ValueError("Invalid label payload size")
    return [math.inf if value == UINT64_MAX else value for value in struct.unpack(f"<{count}Q", payload)]


def membership_bytes(labels, budget):
    mask = bytearray((len(labels) + 7) // 8)
    for state, cost in enumerate(labels):
        if math.isfinite(cost) and (budget is None or cost <= budget):
            mask[state // 8] |= 1 << (state % 8)
    return bytes(mask)
