"""Compact in-memory graph views with byte-compatible canonical JSON and CSR."""

from array import array
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import os
import struct
import sys

from maneuver_graph import ManeuverGraph
from state_graph import nonnegative_integer


class JsonSequence(Sequence):
    def json_rows(self):
        return iter(self)


class Roads(JsonSequence):
    def __init__(self):
        self.ways, self.tails, self.heads = array("Q"), array("Q"), array("Q")
        self.segments, self.costs, self.directions = array("I"), array("I"), array("B")
        self.coordinates, self.names = array("d"), []

    def append(self, road):
        way, segment, direction = road["id"].split(":")
        if int(way) != road["way"] or direction not in {"f", "r"}: raise ValueError("Invalid compact road ID")
        self.ways.append(road["way"]); self.segments.append(int(segment))
        self.tails.append(road["from"]); self.heads.append(road["to"])
        self.costs.append(road["costMs"]); self.directions.append(direction == "r")
        self.coordinates.extend((*road["fromPoint"], *road["toPoint"]))
        self.names.append(road["name"])

    def __len__(self): return len(self.ways)

    def __getitem__(self, index):
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        coordinate = index * 4
        return {"id": f"{self.ways[index]}:{self.segments[index]}:{'r' if self.directions[index] else 'f'}",
                "way": self.ways[index], "from": self.tails[index], "to": self.heads[index], "costMs": self.costs[index],
                "fromPoint": list(self.coordinates[coordinate:coordinate + 2]),
                "toPoint": list(self.coordinates[coordinate + 2:coordinate + 4]), "name": self.names[index]}


class Row(Sequence):
    def __init__(self, graph, start, end): self.graph, self.start, self.end = graph, start, end
    def __len__(self): return self.end - self.start
    def __getitem__(self, index):
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        offset = self.start + index
        return self.graph.targets[offset], self.graph.costs[offset]


class Csr(JsonSequence):
    def __init__(self): self.offsets, self.targets, self.costs = array("I", [0]), array("I"), array("I")
    def append(self, row):
        for target, cost in row:
            nonnegative_integer(target); nonnegative_integer(cost)
            self.targets.append(target); self.costs.append(cost)
        self.offsets.append(len(self.targets))
    def __len__(self): return len(self.offsets) - 1
    def __getitem__(self, index):
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        return Row(self, self.offsets[index], self.offsets[index + 1])
    def json_rows(self): return (list(row) for row in self)


class States(JsonSequence):
    def __init__(self, roads, initial_history): self.count, self.initial_history, self.extra = roads, initial_history, []
    def __len__(self): return self.count + len(self.extra)
    def __getitem__(self, index):
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        road, history = (index, self.initial_history.get(index, ())) if index < self.count else self.extra[index - self.count]
        return {"road": road, "history": list(history)}


ENCODER = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)


def chunks(value):
    if isinstance(value, dict):
        yield "{"
        for index, key in enumerate(sorted(value)):
            if index: yield ","
            yield ENCODER.encode(key); yield ":"
            yield from chunks(value[key])
        yield "}"
    elif isinstance(value, (JsonSequence, range)):
        yield "["
        for index, row in enumerate(value.json_rows() if isinstance(value, JsonSequence) else value):
            if index: yield ","
            yield ENCODER.encode(row)
        yield "]"
    else:
        yield ENCODER.encode(value)


def encoded_blocks(value):
    buffer, size = [], 0
    for chunk in chunks(value):
        buffer.append(chunk); size += len(chunk)
        if size >= 65536:
            yield "".join(buffer).encode(); buffer.clear(); size = 0
    if buffer: yield "".join(buffer).encode()


def digest(value):
    result = hashlib.sha256()
    for block in encoded_blocks(value): result.update(block)
    return result.hexdigest()


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as stream:
        for block in encoded_blocks(value): stream.write(block)
        stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def write_csr(path, graph, identity):
    if not 0 < len(graph) <= 0xFFFFFFFF or len(identity) != 64: raise ValueError("Invalid graph size/identity")
    if any(target >= len(graph) for target in graph.targets): raise ValueError("Invalid arc target")
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as stream:
        stream.write(struct.pack("<8sII32s", b"GPCSR001", len(graph), len(graph.targets), bytes.fromhex(identity)))
        for values in (graph.offsets, graph.targets, graph.costs):
            if sys.byteorder == "little": values.tofile(stream)
            else:
                copy = array("I", values); copy.byteswap(); copy.tofile(stream)
        stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


@dataclass
class BaseGraph:
    roads: Roads
    adjacency: Csr
    blocked_turns: list
    identity: str


def build_maneuver_graph(base, patterns):
    forbidden, prefixes = {}, {()}
    for rule in patterns:
        sequence = tuple(rule["roads"])
        if len(sequence) < 3 or any(type(road) is not int or not 0 <= road < len(base.roads) for road in sequence):
            raise ValueError("A via-way pattern needs at least three known directed roads")
        forbidden.setdefault(sequence, []).append(rule["id"])
        prefixes.update(sequence[:length] for length in range(1, len(sequence)))
    initial_history = {sequence[0]: sequence for sequence in prefixes if len(sequence) == 1}

    def advance(history, following):
        if not history: return initial_history.get(following, ()), []
        sequence = history + (following,)
        rejected = [rule for start in range(len(sequence)) for rule in forbidden.get(sequence[start:], [])]
        suffix = next(sequence[start:] for start in range(len(sequence) + 1) if sequence[start:] in prefixes)
        return suffix, rejected

    states, positions, adjacency, blocked = States(len(base.roads), initial_history), {}, Csr(), []

    def state(road, history):
        if history == initial_history.get(road, ()): return road
        key = road, history
        if key not in positions:
            positions[key] = len(states); states.extra.append(key)
        return positions[key]

    cursor = 0
    while cursor < len(states):
        current = states[cursor]
        row = []
        for following, weight in base.adjacency[current["road"]]:
            history, rejected = advance(tuple(current["history"]), following)
            if rejected: blocked.append({"fromState": cursor, "toRoad": following, "restrictionIds": sorted(rejected)})
            else: row.append((state(following, history), weight))
        adjacency.append(row); cursor += 1
    identity = digest({"model": "exploratory-static-car-v2", "baseIdentity": base.identity,
                       "patterns": patterns, "states": states, "transitions": adjacency})
    return ManeuverGraph(base, states, range(len(base.roads)), adjacency, patterns, blocked, identity)


def build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0):
    """State i means the directed road i has been traversed to its head node."""
    nonnegative_integer(u_turn_ms)
    delays = node_delays or {}
    for delay in delays.values():
        nonnegative_integer(delay)
    outgoing = {}
    seen = set()
    for i, road in enumerate(roads):
        nonnegative_integer(road["costMs"])
        if road["id"] in seen or road["from"] == road["to"]:
            raise ValueError("Road IDs must be unique; self-loop segments are unsupported")
        seen.add(road["id"])
        outgoing.setdefault(road["from"], []).append(i)
    rules = {}
    kinds = {"no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn",
             "no_entry", "no_exit", "only_left_turn", "only_right_turn",
             "only_straight_on", "only_u_turn"}
    for rule in restrictions:
        if rule["kind"] not in kinds:
            raise ValueError("Unsupported turn restriction")
        if rule["fromWay"] == rule["toWay"] and rule["kind"] not in {
            "no_u_turn", "only_u_turn", "no_straight_on", "only_straight_on"
        }:
            raise ValueError("Ambiguous same-way turn restriction")
        rules.setdefault((rule["fromWay"], rule["via"]), []).append(rule)
    adjacency = Csr()
    blocked = set(blocked_nodes)
    blocked_turns = []
    for i, incoming in enumerate(roads):
        node = incoming["to"]
        if node in blocked:
            adjacency.append([])
            continue
        row = []
        for j in outgoing.get(node, []):
            following = roads[j]
            is_reverse = following["to"] == incoming["from"]
            rejected, only_matches = [], []
            for rule in rules.get((incoming["way"], node), []):
                matches = following["way"] == rule["toWay"]
                if rule["fromWay"] == rule["toWay"]:
                    matches = matches and (is_reverse if rule["kind"].endswith("u_turn") else not is_reverse)
                if rule["kind"].startswith("only_"):
                    only_matches.append((rule["id"], matches))
                elif matches:
                    rejected.append(rule["id"])
            if only_matches and not any(matches for _, matches in only_matches):
                rejected.extend(rule_id for rule_id, _ in only_matches)
            if rejected:
                blocked_turns.append({"fromState": i, "toState": j, "restrictionIds": rejected})
                continue
            cost = following["costMs"] + delays.get(node, 0) + (u_turn_ms if is_reverse else 0)
            row.append((j, cost))
        adjacency.append(row)
    del outgoing, seen, rules
    identity = digest({"roads": roads, "transitions": adjacency})
    return BaseGraph(roads, adjacency, blocked_turns, identity)

