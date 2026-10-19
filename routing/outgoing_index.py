"""Versioned outgoing-road CSR index; frozen routing and validation rules."""

from array import array
import sys
import time

from base_ids import build_graph as list_build_graph, ordered_road_ids, stage_marker
from compact_storage import BaseGraph, Csr, digest
from state_graph import nonnegative_integer


MAX_REFERENCES = 0xFFFFFFFF


class OutgoingIndex:
    def __init__(self):
        self.nodes = {}

    def count(self, node):
        self.nodes[node] = self.nodes.get(node, 0) + 1

    def finish(self, tails, mark):
        # Replace counts with ordinals in the same map; retain no second node map.
        self.offsets = array("I", [0]) * (len(self.nodes) + 1)
        total = 0
        for ordinal, (node, count) in enumerate(self.nodes.items()):
            self.offsets[ordinal] = total
            total += count
            self.nodes[node] = ordinal
        self.offsets[-1] = total
        mark("outgoingOffsetsReady")
        cursors = self.offsets[:-1]
        self.references = array("I", [0]) * total
        self.cursor_bytes = sys.getsizeof(cursors)
        mark("outgoingBuffersReady")
        # Match the validated iteration prefix even for incomplete compact rows.
        for road in range(total):
            node = tails[road]
            ordinal = self.nodes[node]
            position = cursors[ordinal]
            self.references[position] = road
            cursors[ordinal] = position + 1
        mark("outgoingFilled")
        del cursors

    def get(self, node, default=None):
        ordinal = self.nodes.get(node)
        if ordinal is None: return default
        return memoryview(self.references)[self.offsets[ordinal]:self.offsets[ordinal + 1]]

    def summary(self):
        return {"outgoingMode": "compact", "outgoingNodes": len(self.nodes),
                "outgoingReferences": len(self.references), "outgoingNodeMaps": 1,
                "outgoingContainerBytes": sum(sys.getsizeof(value) for value in (self.nodes, self.offsets, self.references)),
                "outgoingNodeKeyShallowBytes": sum(sys.getsizeof(node) for node in self.nodes),
                "outgoingOrdinalShallowBytes": sum(sys.getsizeof(ordinal) for ordinal in self.nodes.values()),
                "outgoingArrayPayloadBytes": sum(len(value) * value.itemsize for value in (self.offsets, self.references)),
                "outgoingCursorShallowBytes": self.cursor_bytes}


def build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0,
                id_mode="ordered", measurements=None, observe=None):
    started = time.perf_counter()
    if id_mode not in {"ordered", "strings"}: raise ValueError("Unknown ID storage mode")
    compact = id_mode == "ordered" and ordered_road_ids(roads) and len(roads) <= MAX_REFERENCES
    if not compact:
        result = list_build_graph(roads, restrictions, blocked_nodes, node_delays, u_turn_ms, id_mode, measurements, observe)
        if measurements is not None: measurements["outgoingMode"] = "lists"
        return result
    if measurements is not None:
        measurements.update({"requestedMode": id_mode, "orderedKeyFastPath": True,
                             "idDispatchMs": (time.perf_counter() - started) * 1000, "fallbackToStrings": False})
    return ordered_build_graph(roads, restrictions, blocked_nodes, node_delays, u_turn_ms, measurements, observe)


def ordered_build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0, measurements=None, observe=None):
    """State i means the directed road i has been traversed to its head node."""
    mark = stage_marker(measurements, observe)
    nonnegative_integer(u_turn_ms)
    delays = node_delays or {}
    for delay in delays.values():
        nonnegative_integer(delay)
    outgoing = OutgoingIndex()
    previous = None
    for i, road in enumerate(roads):
        nonnegative_integer(road["costMs"])
        key = roads.ways[i], roads.segments[i], bool(roads.directions[i])
        if key == previous or road["from"] == road["to"]:
            raise ValueError("Road IDs must be unique; self-loop segments are unsupported")
        previous = key
        outgoing.count(road["from"])
    mark("outgoingCounted")
    outgoing.finish(roads.tails, mark)
    if measurements is not None: measurements.update(outgoing.summary())
    if measurements is not None:
        measurements.update({"mode": "ordered", "idKeysRetained": int(previous is not None), "idSetShallowBytes": 0, "idStringShallowBytes": 0})
    mark("outgoingReady")
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
    mark("rulesReady")
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
    mark("arcsBuilt")
    del outgoing, previous, rules
    mark("indexesReleased")
    identity = digest({"roads": roads, "transitions": adjacency})
    mark("baseHashed")
    return BaseGraph(roads, adjacency, blocked_turns, identity)
