"""Explicit road/history states and directed interior destinations for a static model."""

from dataclasses import dataclass
from fractions import Fraction
import math

from anchors import digest
from state_graph import StateGraph


@dataclass
class ManeuverGraph:
    base: StateGraph
    states: list
    initial_states: list
    adjacency: list
    patterns: list
    blocked_turns: list
    identity: str


def build_maneuver_graph(base, patterns):
    """Keep the longest suffix that is a proper prefix of a forbidden road sequence."""
    forbidden, prefixes = {}, {()}
    for rule in patterns:
        sequence = tuple(rule["roads"])
        if len(sequence) < 3 or any(type(road) is not int or not 0 <= road < len(base.roads) for road in sequence):
            raise ValueError("A via-way pattern needs at least three known directed roads")
        forbidden.setdefault(sequence, []).append(rule["id"])
        prefixes.update(sequence[:length] for length in range(1, len(sequence)))

    def advance(history, following):
        sequence = history + (following,)
        rejected = [rule for start in range(len(sequence)) for rule in forbidden.get(sequence[start:], [])]
        suffix = next(sequence[start:] for start in range(len(sequence) + 1) if sequence[start:] in prefixes)
        return suffix, rejected

    states, positions, adjacency, blocked = [], {}, [], []

    def state(road, history):
        key = road, history
        if key not in positions:
            positions[key] = len(states)
            states.append({"road": road, "history": list(history)})
            adjacency.append([])
        return positions[key]

    initial = [state(road, advance((), road)[0]) for road in range(len(base.roads))]
    cursor = 0
    while cursor < len(states):
        current = states[cursor]
        for following, weight in base.adjacency[current["road"]]:
            history, rejected = advance(tuple(current["history"]), following)
            if rejected:
                blocked.append({"fromState": cursor, "toRoad": following, "restrictionIds": sorted(rejected)})
            else:
                adjacency[cursor].append((state(following, history), weight))
        cursor += 1
    identity = digest({"model": "exploratory-static-car-v2", "baseIdentity": base.identity,
                       "patterns": patterns, "states": states, "transitions": adjacency})
    return ManeuverGraph(base, states, initial, adjacency, patterns, blocked, identity)


def source_seeds(graph, starts):
    """Starts are (directed road, fraction from its tail), with no pre-trip history."""
    if not starts:
        raise ValueError("At least one source attachment is required")
    seeds = []
    for road, fraction in starts:
        if type(road) is not int or not 0 <= road < len(graph.base.roads):
            raise ValueError("Unknown source road")
        fraction = Fraction(fraction)
        if not 0 <= fraction <= 1:
            raise ValueError("Source fraction must be between zero and one")
        seeds.append((graph.initial_states[road], math.ceil(graph.base.roads[road]["costMs"] * (1 - fraction))))
    return seeds


def interior_destination(graph, labels, road, fraction, starts=()):
    """Stop inside a directed road, paying only legal entry and its partial traversal."""
    if len(labels) != len(graph.states) or type(road) is not int or not 0 <= road < len(graph.base.roads):
        raise ValueError("Destination requires matching labels and a known road")
    fraction = Fraction(fraction)
    if not 0 < fraction < 1:
        raise ValueError("Interior fraction must be strictly between zero and one")
    full_cost = graph.base.roads[road]["costMs"]
    partial_cost = math.ceil(full_cost * fraction)
    best = math.inf
    for incoming, row in enumerate(graph.adjacency):
        if not math.isfinite(labels[incoming]):
            continue
        for target, weight in row:
            if graph.states[target]["road"] == road:
                # This transition has already passed both via-node and history rules.
                best = min(best, labels[incoming] + weight - full_cost + partial_cost)
    for source, offset in starts:
        offset = Fraction(offset)
        source_seeds(graph, [(source, offset)])  # Validate the attachment, including its fraction.
        if source == road and offset <= fraction:
            best = min(best, math.ceil(full_cost * (fraction - offset)))
    return best


def destination_oracle(graph, seeds, road, fraction, starts):
    """Add a terminal sink and use flat-edge Bellman–Ford, independently of cost labels."""
    from state_graph import bellman_ford

    fraction = Fraction(fraction)
    if not 0 < fraction < 1:
        raise ValueError("Oracle destination must be interior")
    sink = len(graph.states)
    adjacency = [list(row) for row in graph.adjacency] + [[]]
    cost = graph.base.roads[road]["costMs"]
    for state, row in enumerate(graph.adjacency):
        for target, weight in row:
            if graph.states[target]["road"] == road:
                adjacency[state].append((sink, weight - cost + math.ceil(cost * fraction)))
    attachments = list(seeds)
    for source, offset in starts:
        if source == road and Fraction(offset) <= fraction:
            attachments.append((sink, math.ceil(cost * (fraction - Fraction(offset)))))
    return bellman_ford(adjacency, attachments)[sink]


def replay(graph, roads, fraction=Fraction(0)):
    """Replay a specified maneuver; a blocked step is not proof that no detour exists."""
    current, cost = source_seeds(graph, [(roads[0], fraction)])[0]
    trace = [current]
    for step, road in enumerate(roads[1:], 1):
        options = [(target, weight) for target, weight in graph.adjacency[current] if graph.states[target]["road"] == road]
        if not options:
            return {"allowed": False, "blockedStep": step, "states": trace, "costBeforeBlockedMs": cost}
        if len(options) != 1:
            raise ValueError("Ambiguous maneuver replay")
        current, weight = options[0]
        cost += weight
        trace.append(current)
    return {"allowed": True, "states": trace, "costMs": cost}
