"""Versioned base builder with bounded ID state on ordered compact roads."""

import sys
import time

from compact_storage import BaseGraph, Csr, Roads, digest
from state_graph import nonnegative_integer


def stage_marker(measurements, observe):
    previous = time.perf_counter()

    def mark(stage):
        nonlocal previous
        now = time.perf_counter()
        if measurements is not None: measurements.setdefault("phaseMs", {})[stage] = (now - previous) * 1000
        if observe: observe(stage)
        previous = time.perf_counter()

    return mark


def ordered_road_ids(roads):
    # Only the exact compact class guarantees that its numeric key is its ID.
    if type(roads) is not Roads: return False
    if len(roads.segments) != len(roads) or len(roads.directions) != len(roads): return False
    previous = None
    for key in zip(roads.ways, roads.segments, map(bool, roads.directions)):
        if previous is not None and key < previous: return False
        previous = key
    return True


def build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0,
                id_mode="ordered", measurements=None, observe=None):
    started = time.perf_counter()
    if id_mode not in {"ordered", "strings"}: raise ValueError("Unknown ID storage mode")
    ordered = id_mode == "ordered" and ordered_road_ids(roads)
    if measurements is not None:
        measurements.update({"requestedMode": id_mode, "orderedKeyFastPath": ordered,
                             "idDispatchMs": (time.perf_counter() - started) * 1000})
    function = ordered_build_graph if ordered else string_build_graph
    result = function(roads, restrictions, blocked_nodes, node_delays, u_turn_ms, measurements, observe)
    if measurements is not None: measurements["fallbackToStrings"] = id_mode == "ordered" and not ordered
    return result


def string_build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0, measurements=None, observe=None):
    """State i means the directed road i has been traversed to its head node."""
    mark = stage_marker(measurements, observe)
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
    if measurements is not None:
        measurements.update({"outgoingNodes": len(outgoing), "outgoingReferences": sum(len(row) for row in outgoing.values()),
                             "outgoingContainerBytes": sys.getsizeof(outgoing) + sum(sys.getsizeof(row) for row in outgoing.values())})
    if measurements is not None:
        measurements.update({"mode": "strings", "idKeysRetained": len(seen), "idSetShallowBytes": sys.getsizeof(seen),
                             "idStringShallowBytes": sum(sys.getsizeof(value) for value in seen)})
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
    del outgoing, seen, rules
    mark("indexesReleased")
    identity = digest({"roads": roads, "transitions": adjacency})
    mark("baseHashed")
    return BaseGraph(roads, adjacency, blocked_turns, identity)


def ordered_build_graph(roads, restrictions=(), blocked_nodes=(), node_delays=None, u_turn_ms=0, measurements=None, observe=None):
    """State i means the directed road i has been traversed to its head node."""
    mark = stage_marker(measurements, observe)
    nonnegative_integer(u_turn_ms)
    delays = node_delays or {}
    for delay in delays.values():
        nonnegative_integer(delay)
    outgoing = {}
    previous = None
    for i, road in enumerate(roads):
        nonnegative_integer(road["costMs"])
        key = roads.ways[i], roads.segments[i], bool(roads.directions[i])
        if key == previous or road["from"] == road["to"]:
            raise ValueError("Road IDs must be unique; self-loop segments are unsupported")
        previous = key
        outgoing.setdefault(road["from"], []).append(i)
    if measurements is not None:
        measurements.update({"outgoingNodes": len(outgoing), "outgoingReferences": sum(len(row) for row in outgoing.values()),
                             "outgoingContainerBytes": sys.getsizeof(outgoing) + sum(sys.getsizeof(row) for row in outgoing.values())})
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
