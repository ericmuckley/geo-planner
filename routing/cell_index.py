"""Conservative directed cell bounds with measured local range reads."""

import heapq
import math
import os
import struct
import time

from anchors import UNKNOWN, atomic_write, file_hash, load_json, save_json
from state_graph import nonnegative_integer, validate_index, validate_seeds


def stored(value):
    if value == math.inf:
        return UNKNOWN
    nonnegative_integer(value)
    if value >= UNKNOWN:
        raise ValueError("Cost exceeds uint32 capacity")
    return value


def restored(value):
    return math.inf if value == UNKNOWN else value


def build_cells(graph, index, leaf_size, directory):
    validate_index(graph, index)
    if not isinstance(leaf_size, int) or isinstance(leaf_size, bool) or leaf_size < 1:
        raise ValueError("Leaf size must be a positive integer")
    count, landmarks = len(graph.roads), len(index.states)
    fields = [field.labels for field in index.forward + index.backward]
    order, nodes = [], []

    def build(states):
        node_id = len(nodes)
        nodes.append(None)
        if len(states) <= leaf_size:
            start = len(order)
            order.extend(states)
            summaries = []
            for a in range(landmarks):
                forward = [fields[a][state] for state in states]
                reverse = [fields[landmarks + a][state] for state in states]
                summaries.extend((min(forward), max(forward), min(reverse), max(reverse)))
            nodes[node_id] = (-1, -1, start, len(order), summaries)
        else:
            points = [graph.roads[s]["toPoint"] for s in states]
            spans = [max(p[axis] for p in points) - min(p[axis] for p in points) for axis in (0, 1)]
            axis = 0 if spans[0] >= spans[1] else 1
            states = sorted(states, key=lambda s: (graph.roads[s]["toPoint"][axis], s))
            middle = len(states) // 2
            left, right = build(states[:middle]), build(states[middle:])
            summaries = []
            for i in range(0, 4 * landmarks, 4):
                a, b = nodes[left][4][i:i + 4], nodes[right][4][i:i + 4]
                summaries.extend((min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3])))
            nodes[node_id] = (left, right, nodes[left][2], nodes[right][3], summaries)
        return node_id

    build(list(range(count)))
    positions = [0] * count
    for position, state in enumerate(order):
        positions[state] = position
    node_struct = struct.Struct(f"<iiII{4 * landmarks}I")
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write(directory / "cells.bin", b"".join(node_struct.pack(left, right, start, end, *map(stored, summary))
                                                 for left, right, start, end, summary in nodes))
    for name, values in (("states.u32le", order), ("positions.u32le", positions)):
        atomic_write(directory / name, struct.pack(f"<{count}I", *values))
    atomic_write(directory / "details.bin", b"".join(struct.pack(f"<{2 * landmarks}I", *(stored(field[state]) for field in fields)) for state in order))
    files = ("cells.bin", "states.u32le", "positions.u32le", "details.bin")
    manifest = {"schemaVersion": 1, "graphIdentity": graph.identity, "completeFields": True,
                "stateCount": count, "landmarkCount": landmarks, "landmarkStates": index.states,
                "leafSize": leaf_size, "nodeCount": len(nodes), "nodeRecordBytes": node_struct.size,
                "partition": "deterministic median split on largest longitude/latitude span; state head coordinates",
                "artifacts": {name: {"bytes": (directory / name).stat().st_size, "sha256": file_hash(directory / name)} for name in files}}
    save_json(directory / "manifest.json", manifest)
    return manifest, order


def verify_cells(directory, graph_identity):
    manifest = load_json(directory / "manifest.json")
    if manifest["schemaVersion"] != 1 or manifest["graphIdentity"] != graph_identity or not manifest["completeFields"]:
        raise ValueError("Cell index requires matching graph and complete fields")
    if manifest["nodeRecordBytes"] != 16 + 16 * manifest["landmarkCount"]:
        raise ValueError("Invalid cell record size")
    for name in ("cells.bin", "states.u32le", "positions.u32le", "details.bin"):
        expected = manifest["artifacts"][name]
        path = directory / name
        if path.stat().st_size != expected["bytes"] or file_hash(path) != expected["sha256"]:
            raise ValueError(f"Cell index checksum mismatch: {name}")
    count = manifest["stateCount"]
    expected_sizes = {"cells.bin": manifest["nodeCount"] * manifest["nodeRecordBytes"],
                      "states.u32le": 4 * count, "positions.u32le": 4 * count,
                      "details.bin": 8 * count * manifest["landmarkCount"]}
    if any(manifest["artifacts"][name]["bytes"] != size for name, size in expected_sizes.items()):
        raise ValueError("Cell artifact size mismatch")
    return manifest


class CellReader:
    """Preflight once, then count actual pread requests/bytes for each fresh query."""

    def __init__(self, directory, manifest):
        self.manifest = manifest
        self.descriptors = {}
        self.bytes = self.reads = 0
        self.nodes_read = self.detail_states = 0
        self.node_struct = struct.Struct(f"<iiII{4 * manifest['landmarkCount']}I")
        self.state_struct = struct.Struct(f"<{2 * manifest['landmarkCount']}I")
        try:
            for name in ("cells.bin", "states.u32le", "positions.u32le", "details.bin"):
                self.descriptors[name] = os.open(directory / name, os.O_RDONLY)
        except Exception:
            self.close()
            raise

    def close(self):
        for descriptor in self.descriptors.values():
            os.close(descriptor)
        self.descriptors.clear()

    def read(self, name, offset, length):
        data = os.pread(self.descriptors[name], length, offset)
        self.reads += 1
        self.bytes += len(data)
        if len(data) != length:
            raise ValueError(f"Incomplete range read: {name}")
        return data

    def source(self, state):
        position, = struct.unpack("<I", self.read("positions.u32le", state * 4, 4))
        if position >= self.manifest["stateCount"]:
            raise ValueError("Invalid source position")
        return tuple(map(restored, self.state_struct.unpack(self.read("details.bin", position * self.state_struct.size, self.state_struct.size))))

    def node(self, node_id):
        if not 0 <= node_id < self.manifest["nodeCount"]:
            raise ValueError("Invalid child cell")
        record = self.node_struct.unpack(self.read("cells.bin", node_id * self.node_struct.size, self.node_struct.size))
        left, right, start, end = record[:4]
        if not 0 <= start < end <= self.manifest["stateCount"] or ((left == -1) != (right == -1)):
            raise ValueError("Invalid cell state range")
        self.nodes_read += 1
        return left, right, start, end, tuple(map(restored, record[4:]))

    def detail(self, start, end):
        count = end - start
        states = struct.unpack(f"<{count}I", self.read("states.u32le", start * 4, count * 4))
        values = self.read("details.bin", start * self.state_struct.size, count * self.state_struct.size)
        self.detail_states += count
        return zip(states, (tuple(map(restored, row)) for row in self.state_struct.iter_unpack(values)))


def summary_bounds(sources, summary):
    """Bounds hold for every state in this cell; complete-field infinity is deliberate."""
    lower = upper = math.inf
    landmarks = len(summary) // 4
    for attachment, source in sources:
        low, high = 0, math.inf
        for a in range(landmarks):
            min_f, max_f, _, max_r = summary[4 * a:4 * a + 4]
            fs, rs = source[a], source[landmarks + a]
            if math.isfinite(fs):
                low = max(low, min_f - fs)
            if math.isfinite(max_r):
                low = max(low, rs - max_r)
            if math.isfinite(rs) and math.isfinite(max_f):
                high = min(high, rs + max_f)
        lower, upper = min(lower, attachment + low), min(upper, attachment + high)
    return lower, upper


def decision(lower, upper, budget):
    return "reachable" if upper <= budget else "unreachable" if lower > budget else "unresolved"


def classify_cells(reader, seeds, budget):
    validate_seeds(reader.manifest["stateCount"], seeds)
    nonnegative_integer(budget)
    sources = [(attachment, reader.source(state)) for state, attachment in seeds]
    groups, states, unresolved = [], {}, set()
    queue = [0]
    visited = set()
    summary_counts = {"reachable": 0, "unreachable": 0}
    before = time.perf_counter()
    leaves = []
    while queue:
        node_id = queue.pop()
        if node_id in visited:
            raise ValueError("Cell tree contains a cycle or shared child")
        visited.add(node_id)
        left, right, start, end, summary = reader.node(node_id)
        lower, upper = summary_bounds(sources, summary)
        result = decision(lower, upper, budget)
        if result != "unresolved":
            groups.append((start, end, result, lower, upper))
            summary_counts[result] += end - start
        elif left == -1:
            leaves.append((start, end))
        else:
            queue.extend((right, left))
    summary_ms = (time.perf_counter() - before) * 1000
    before = time.perf_counter()
    landmarks = reader.manifest["landmarkCount"]
    for start, end in leaves:
        for state, row in reader.detail(start, end):
            summary = tuple(value for a in range(landmarks) for value in (row[a], row[a], row[landmarks + a], row[landmarks + a]))
            lower, upper = summary_bounds(sources, summary)
            result = decision(lower, upper, budget)
            states[state] = (result, lower, upper)
            if result == "unresolved":
                unresolved.add(state)
    detail_ms = (time.perf_counter() - before) * 1000
    return {"groups": groups, "states": states, "unresolved": unresolved,
            "summaryCertified": summary_counts, "summaryMs": summary_ms, "detailMs": detail_ms}


def refine_targets(adjacency, seeds, budget, targets):
    """Stop when all unknown targets settle; certified cells remain valid transit paths."""
    validate_seeds(len(adjacency), seeds)
    nonnegative_integer(budget)
    pending = set(targets)
    if any(not isinstance(s, int) or isinstance(s, bool) or not 0 <= s < len(adjacency) for s in pending):
        raise ValueError("Unknown refinement target")
    queue, labels, reached = [], {}, set()
    for state, cost in seeds:
        if cost <= budget and cost < labels.get(state, math.inf):
            labels[state] = cost
            heapq.heappush(queue, (cost, state))
    settled = scanned = 0
    while queue and pending:
        cost, state = heapq.heappop(queue)
        if cost != labels[state]:
            continue
        settled += 1
        if state in pending:
            reached.add(state)
            pending.remove(state)
            if not pending:
                break
        for target, weight in adjacency[state]:
            scanned += 1
            candidate = cost + weight
            if candidate <= budget and candidate < labels.get(target, math.inf):
                labels[target] = candidate
                heapq.heappush(queue, (candidate, target))
    return reached, {"settledStates": settled, "scannedArcs": scanned, "allTargetsSettled": bool(targets) and not pending}


def materialize(result, order, refined):
    """Verification/output expansion; intentionally measured apart from compact query results."""
    membership = [None] * len(order)
    for start, end, status, _, _ in result["groups"]:
        for position in range(start, end):
            state = order[position]
            if membership[state] is not None:
                raise ValueError("Overlapping cell results")
            membership[state] = status == "reachable"
    for state, (status, _, _) in result["states"].items():
        if membership[state] is not None:
            raise ValueError("Overlapping detailed result")
        membership[state] = state in refined if status == "unresolved" else status == "reachable"
    if any(value is None for value in membership):
        raise ValueError("Incomplete result coverage")
    return membership
