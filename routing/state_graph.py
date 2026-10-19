"""Small static turn-aware reference and directed landmark certificates."""

from dataclasses import dataclass
from fractions import Fraction
import heapq
import math
import struct

from anchors import UNKNOWN, digest


def nonnegative_integer(value):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("Costs/budgets must be nonnegative integer milliseconds")


@dataclass
class StateGraph:
    roads: list
    adjacency: list
    reverse: list
    blocked_turns: list
    identity: str


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
    adjacency = [[] for _ in roads]
    reverse = [[] for _ in roads]
    blocked = set(blocked_nodes)
    blocked_turns = []
    for i, incoming in enumerate(roads):
        node = incoming["to"]
        if node in blocked:
            continue
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
            adjacency[i].append((j, cost))
            reverse[j].append((i, cost))
    identity = digest({"roads": roads, "transitions": adjacency})
    return StateGraph(roads, adjacency, reverse, blocked_turns, identity)


def validate_seeds(count, seeds):
    if not seeds:
        raise ValueError("At least one permitted directed source state is required")
    for state, cost in seeds:
        if not isinstance(state, int) or isinstance(state, bool) or not 0 <= state < count:
            raise ValueError("Unknown source state")
        nonnegative_integer(cost)


@dataclass
class SearchResult:
    labels: list
    complete: bool
    horizon_ms: int | None
    settled_states: int
    scanned_arcs: int


def dijkstra(adjacency, seeds, budget_ms=None):
    validate_seeds(len(adjacency), seeds)
    if budget_ms is not None:
        nonnegative_integer(budget_ms)
    labels = [math.inf] * len(adjacency)
    queue = []
    for state, cost in seeds:
        if cost < labels[state] and (budget_ms is None or cost <= budget_ms):
            labels[state] = cost
            heapq.heappush(queue, (cost, state))
    settled = scanned = 0
    while queue:
        cost, state = heapq.heappop(queue)
        if cost != labels[state]:
            continue
        settled += 1
        for target, weight in adjacency[state]:
            scanned += 1
            candidate = cost + weight
            if candidate < labels[target] and (budget_ms is None or candidate <= budget_ms):
                labels[target] = candidate
                heapq.heappush(queue, (candidate, target))
    return SearchResult(labels, budget_ms is None, budget_ms, settled, scanned)


def bellman_ford(adjacency, seeds):
    """Independent flat-edge relaxation oracle; deliberately no heap/Dijkstra calls."""
    validate_seeds(len(adjacency), seeds)
    labels = [math.inf] * len(adjacency)
    for state, cost in seeds:
        labels[state] = min(labels[state], cost)
    arcs = [(source, target, weight) for source, row in enumerate(adjacency) for target, weight in row]
    for _ in range(len(adjacency) - 1):
        changed = False
        for source, target, weight in arcs:
            candidate = labels[source] + weight
            if candidate < labels[target]:
                labels[target] = candidate
                changed = True
        if not changed:
            break
    return labels


def partial_source(graph, state, fraction):
    validate_seeds(len(graph.roads), [(state, 0)])
    fraction = Fraction(fraction)
    if not 0 <= fraction <= 1:
        raise ValueError("Source fraction must be between zero and one")
    # No fresh heading choice at the next junction: retain the incoming state.
    remaining = math.ceil(graph.roads[state]["costMs"] * (1 - fraction))
    return [(state, remaining)]


@dataclass
class LandmarkIndex:
    graph_identity: str
    states: list
    forward: list
    backward: list


def landmark_index(graph, states):
    if not states or len(set(states)) != len(states):
        raise ValueError("Landmarks must be distinct states")
    forward, backward = [], []
    for state in states:
        forward.append(dijkstra(graph.adjacency, [(state, 0)]))
        backward.append(dijkstra(graph.reverse, [(state, 0)]))
    return LandmarkIndex(graph.identity, list(states), forward, backward)


def validate_index(graph, index):
    if index.graph_identity != graph.identity:
        raise ValueError("Landmark index belongs to a different graph/model")
    if not len(index.states) == len(index.forward) == len(index.backward):
        raise ValueError("Incomplete landmark index")
    for field in index.forward + index.backward:
        if not field.complete or field.horizon_ms is not None or len(field.labels) != len(graph.roads):
            raise ValueError("Exact certificates require complete, untruncated landmark fields")


def pack_index(graph, index):
    validate_index(graph, index)
    packed = bytearray()
    for field in index.forward + index.backward:
        for value in field.labels:
            if value != math.inf:
                nonnegative_integer(value)
                if value >= UNKNOWN:
                    raise ValueError("Landmark field exceeds uint32 millisecond capacity")
            packed.extend(struct.pack("<I", UNKNOWN if value == math.inf else value))
    return bytes(packed)


def unpack_index(graph, states, data, graph_identity, complete):
    if graph_identity != graph.identity or not complete:
        raise ValueError("Packed fields require the matching graph and complete-search metadata")
    if not states or len(set(states)) != len(states):
        raise ValueError("Landmarks must be distinct states")
    validate_seeds(len(graph.roads), [(state, 0) for state in states])
    count = len(graph.roads)
    if len(data) != 2 * len(states) * count * 4:
        raise ValueError("Packed landmark field size mismatch")
    values = [math.inf if value == UNKNOWN else value for (value,) in struct.iter_unpack("<I", data)]
    fields = [SearchResult(values[i:i + count], True, None, 0, 0) for i in range(0, len(values), count)]
    return LandmarkIndex(graph.identity, list(states), fields[:len(states)], fields[len(states):])


def state_bounds(source, target, index):
    lower, upper = 0, math.inf
    for forward, backward in zip(index.forward, index.backward):
        fs, ft = forward.labels[source], forward.labels[target]
        rs, rt = backward.labels[source], backward.labels[target]
        if math.isfinite(fs):
            lower = max(lower, ft - fs)  # inf - finite proves disconnection in this graph.
        if math.isfinite(rt):
            lower = max(lower, rs - rt)
        if math.isfinite(rs) and math.isfinite(ft):
            upper = min(upper, rs + ft)
    return lower, upper


def classify(graph, index, seeds, budget_ms):
    validate_index(graph, index)
    validate_seeds(len(graph.roads), seeds)
    nonnegative_integer(budget_ms)
    decisions = []
    for target in range(len(graph.roads)):
        lower = upper = math.inf
        # A coordinate with several permitted starts is a union/minimum, not an intersection.
        for source, attachment in seeds:
            low, high = state_bounds(source, target, index)
            lower = min(lower, attachment + low)
            upper = min(upper, attachment + high)
        decision = "reachable" if upper <= budget_ms else "unreachable" if lower > budget_ms else "unresolved"
        decisions.append((decision, lower, upper))
    return decisions
