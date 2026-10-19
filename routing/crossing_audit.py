"""Source-marked border uncertainty and legal-in-model route diagnostics."""

from fractions import Fraction
import math
import xml.etree.ElementTree as ET

from import_roads import tags
from maneuver_graph import replay


UNCERTAIN_REASON = "source-marked-crossing-access-uncertainty"


def uncertainty_reason(properties):
    note = properties.get("fixme", "").lower()
    if any(word in note for word in ("border", "checkpoint")) and any(word in note for word in ("access", "barrier")):
        return UNCERTAIN_REASON
    return None


def source_uncertainties(source, destination):
    """Keep complete original uncertain ways and referenced nodes in a small excerpt."""
    selected, way_xml, node_ids = [], [], set()
    parser = ET.iterparse(source, events=("start", "end")); _, root = next(parser)
    for event, element in parser:
        if event == "end" and element.tag in {"node", "way", "relation"}:
            if element.tag == "way":
                properties = tags(element)
                reason = uncertainty_reason(properties)
                if reason:
                    nodes = [int(node.get("ref")) for node in element.findall("nd")]
                    selected.append({"id": int(element.get("id")), "tags": properties, "nodes": nodes, "reason": reason})
                    way_xml.append(ET.tostring(element))
                    node_ids.update(nodes)
            root.remove(element)
    with destination.open("wb") as stream:
        stream.write(b'<osm version="0.6">\n')
        parser = ET.iterparse(source, events=("start", "end")); _, root = next(parser)
        for event, element in parser:
            if event == "end" and element.tag in {"node", "way", "relation"}:
                if element.tag == "node" and int(element.get("id")) in node_ids: stream.write(ET.tostring(element))
                root.remove(element)
        for element in way_xml: stream.write(element)
        stream.write(b'</osm>\n')
    return selected


def barrier_examples(graph, audit, node_ids):
    incoming, outgoing = {node: [] for node in node_ids}, {node: [] for node in node_ids}
    for index, road in enumerate(graph.base.roads):
        if road["to"] in incoming: incoming[road["to"]].append(index)
        if road["from"] in outgoing: outgoing[road["from"]].append(index)
    decisions = {row["id"]: row for row in audit["barrierPolicy"]["decisions"]}
    examples = []
    for node in sorted(node_ids):
        decision = decisions[node]
        turns = [{"fromRoadId": graph.base.roads[left]["id"], "toRoadId": graph.base.roads[right]["id"],
                  "uTurn": graph.base.roads[left]["from"] == graph.base.roads[right]["to"], **replay(graph, [left, right])}
                 for left in incoming[node] for right in outgoing[node]]
        if decision["blockedByModel"] and any(turn["allowed"] for turn in turns): raise ValueError("Closed barrier has a legal departure")
        examples.append({**decision, "incomingRoadIds": [graph.base.roads[index]["id"] for index in incoming[node]],
                         "outgoingRoadIds": [graph.base.roads[index]["id"] for index in outgoing[node]], "transitions": turns})
    return examples


def route_evidence(graph, origin, route, uncertainties, opened_nodes):
    """Recompute a full history-state witness, retaining its partial destination cost."""
    if route["costMs"] is None:
        return {"reachableInModel": False, "sourceUncertaintyWayIds": [], "carEligibilityVerified": False}
    path = route["states"]
    if not path: raise ValueError("This diagnostic requires distinct graph-attached endpoints")
    cost = min(cost for state, cost in origin["seeds"] if state == path[0])
    visited, ways = [], set()
    for left, right in zip(path, path[1:]):
        cost += next(weight for target, weight in graph.adjacency[left] if target == right)
        node = graph.base.roads[graph.states[left]["road"]]["to"]
        if node in opened_nodes: visited.append(node)
    roads = [graph.base.roads[graph.states[state]["road"]] for state in path]
    if [road["id"] for road in roads] != route["roadIds"]: raise ValueError("Route road/history states differ")
    last = roads[-1]
    if last["id"] != route["targetRoadId"]: raise ValueError("Route target differs from terminal state")
    cost += math.ceil(last["costMs"] * Fraction(route["targetFraction"])) - last["costMs"]
    if cost != route["costMs"]: raise ValueError("Recovered route cost differs")
    ways.update(road["way"] for road in roads)
    hits = sorted(ways.intersection(row["id"] for row in uncertainties))
    return {"reachableInModel": True, "recomputedCostMs": cost, "sourceUncertaintyWayIds": hits,
            "qualifiedStaticBarrierNodesTraversed": visited, "carEligibilityVerified": False,
            "eligibilityScope": "Source hints on this witness only; absence of a hint is not verified real access. No queue/delay/document evaluation."}
