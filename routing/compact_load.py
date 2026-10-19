"""Reload canonical graph JSON one array element at a time into compact views."""

import json

from compact_storage import BaseGraph, Csr, Roads, States, digest
from maneuver_graph import ManeuverGraph


class Reader:
    def __init__(self, stream, block_size=1 << 20):
        self.stream, self.block_size, self.buffer, self.offset, self.eof = stream, block_size, "", 0, False
        self.decoder = json.JSONDecoder()

    def fill(self):
        self.buffer = self.buffer[self.offset:]; self.offset = 0
        block = self.stream.read(self.block_size)
        self.buffer += block
        if not block: self.eof = True

    def peek(self):
        while True:
            while self.offset < len(self.buffer) and self.buffer[self.offset].isspace(): self.offset += 1
            if self.offset < len(self.buffer): return self.buffer[self.offset]
            if self.eof: return ""
            self.fill()

    def take(self, character):
        if self.peek() != character: raise ValueError(f"Expected JSON delimiter {character}")
        self.offset += 1

    def value(self):
        first = self.peek()
        while True:
            if first and first in "-0123456789":
                boundary = self.offset
                while boundary < len(self.buffer) and self.buffer[boundary] not in ",]} \r\n\t:": boundary += 1
                if boundary == len(self.buffer) and not self.eof:
                    self.fill(); continue
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.offset)
            except json.JSONDecodeError:
                if self.eof: raise
                self.fill(); continue
            # A numeric token might continue in the next read block.
            if end == len(self.buffer) and not self.eof:
                self.fill(); continue
            if end < len(self.buffer) and self.buffer[end] not in ",]} \r\n\t:": raise ValueError("Invalid JSON token boundary")
            self.offset = end
            return value

    def rows(self):
        self.take("[")
        if self.peek() != "]":
            while True:
                yield self.value()
                if self.peek() == "]": break
                self.take(",")
        self.take("]")


def load_graph(path, block_size=1 << 20):
    data, roads, base_rows, rows, states, initial_count = {}, Roads(), Csr(), Csr(), None, 0
    seen = set()
    with path.open() as stream:
        reader = Reader(stream, block_size)
        reader.take("{")
        while True:
            key = reader.value()
            if key in seen: raise ValueError("Duplicate graph field")
            seen.add(key); reader.take(":")
            if key == "roads":
                for row in reader.rows(): roads.append(row)
            elif key in {"baseTransitions", "transitions"}:
                target = base_rows if key == "baseTransitions" else rows
                for row in reader.rows(): target.append(row)
            elif key == "initialStates":
                for index in reader.rows():
                    if type(index) is not int or index != initial_count: raise ValueError("Initial state ordering differs")
                    initial_count += 1
            elif key == "states":
                if "roads" not in seen: raise ValueError("Canonical graph requires roads before states")
                states = States(len(roads), {})
                count = 0
                for row in reader.rows():
                    if count < len(roads):
                        if row["road"] != count: raise ValueError("Initial road/state ordering differs")
                        if row["history"]: states.initial_history[count] = tuple(row["history"])
                    else: states.extra.append((row["road"], tuple(row["history"])))
                    count += 1
                if count != len(states): raise ValueError("Incomplete states")
            elif key in {"model", "baseIdentity", "graphIdentity", "patterns"}: data[key] = reader.value()
            else: raise ValueError(f"Unknown graph field {key}")
            if reader.peek() == "}": break
            reader.take(",")
        reader.take("}")
        if reader.peek(): raise ValueError("Trailing graph data")
    expected = {"roads", "baseTransitions", "transitions", "states", "initialStates", "model", "baseIdentity", "graphIdentity", "patterns"}
    if seen != expected or states is None or initial_count != len(roads) or len(base_rows) != len(roads) or len(rows) != len(states):
        raise ValueError("Incomplete compact graph")
    base_id = digest({"roads": roads, "transitions": base_rows})
    graph_id = digest({"model": data["model"].get("id", "exploratory-static-car-v2"), "baseIdentity": base_id, "patterns": data["patterns"], "states": states, "transitions": rows})
    if base_id != data["baseIdentity"] or graph_id != data["graphIdentity"]: raise ValueError("Reloaded identity differs")
    return ManeuverGraph(BaseGraph(roads, base_rows, [], base_id), states, range(len(roads)), rows, data["patterns"], [], graph_id), data["model"]
