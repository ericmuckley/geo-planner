"""Outgoing offsets indexed by the existing sorted OSM node array."""

from array import array
from bisect import bisect_left
import sys
import time

from base_ids import ordered_road_ids, stage_marker
from compact_storage import BaseGraph, Csr, digest
from outgoing_index import MAX_REFERENCES, build_graph as frozen_build_graph
from state_graph import nonnegative_integer


class SourceOutgoingIndex:
    def __init__(self, node_ids):
        self.node_ids = node_ids
        self.offsets = array("I", [0]) * (len(node_ids) + 1)
        self.active_nodes = 0

    def position(self, node):
        position = bisect_left(self.node_ids, node)
        return position if position < len(self.node_ids) and self.node_ids[position] == node else None

    def count(self, node):
        position = self.position(node)
        if position is None: raise ValueError("Outgoing road node is missing from source IDs")
        slot = position + 1
        self.active_nodes += self.offsets[slot] == 0
        self.offsets[slot] += 1

    def finish(self, tails, mark):
        total = 0
        for index in range(1, len(self.offsets)):
            total += self.offsets[index]
            self.offsets[index] = total
        mark("outgoingOffsetsReady")
        cursors = self.offsets[:-1]
        self.references = array("I", [0]) * total
        self.cursor_bytes = sys.getsizeof(cursors)
        mark("outgoingBuffersReady")
        for road in range(total):
            ordinal = self.position(tails[road])
            position = cursors[ordinal]
            self.references[position] = road
            cursors[ordinal] = position + 1
        mark("outgoingFilled")
        del cursors

    def get(self, node, default=None):
        ordinal = self.position(node)
        if ordinal is None or self.offsets[ordinal] == self.offsets[ordinal + 1]: return default
        return memoryview(self.references)[self.offsets[ordinal]:self.offsets[ordinal + 1]]

    def summary(self):
        return {"outgoingMode": "source-sorted", "outgoingNodes": self.active_nodes,
                "outgoingSourceNodes": len(self.node_ids), "outgoingReferences": len(self.references),
                "outgoingNodeMaps": 0, "outgoingBorrowedNodeIdPayloadBytes": len(self.node_ids) * self.node_ids.itemsize,
                "outgoingContainerBytes": sys.getsizeof(self.offsets) + sys.getsizeof(self.references),
                "outgoingNodeKeyShallowBytes": 0, "outgoingOrdinalShallowBytes": 0,
                "outgoingArrayPayloadBytes": sum(len(value) * value.itemsize for value in (self.offsets, self.references)),
                "outgoingCursorShallowBytes": self.cursor_bytes}


def valid_source_ids(node_ids):
    if type(node_ids) is not array or node_ids.typecode not in {"q", "Q"}: return False
    previous = None
    for node in node_ids:
        if previous is not None and node <= previous: return False
        previous = node
    return True


def build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0,
                id_mode="ordered", measurements=None, observe=None, node_ids=None):
    started = time.perf_counter()
    if (id_mode != "ordered" or not valid_source_ids(node_ids) or
            not ordered_road_ids(roads) or len(roads) > MAX_REFERENCES):
        return frozen_build_graph(roads, restrictions, blocked_nodes, node_delays, u_turn_ms, id_mode, measurements, observe)
    if measurements is not None:
        measurements.update(requestedMode=id_mode, orderedKeyFastPath=True,
                            idDispatchMs=(time.perf_counter() - started) * 1000, fallbackToStrings=False)
    return ordered_build_graph(roads, restrictions, blocked_nodes, node_delays, u_turn_ms, measurements, observe, node_ids)


def ordered_build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0, measurements=None, observe=None, node_ids=None):
    """State i means the directed road i has been traversed to its head node."""
    mark = stage_marker(measurements, observe)
    nonnegative_integer(u_turn_ms)
    delays = node_delays or {}
    for delay in delays.values():
        nonnegative_integer(delay)
    outgoing = SourceOutgoingIndex(node_ids)
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
