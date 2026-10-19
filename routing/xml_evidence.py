"""Frozen source evidence with explicit range-aware, read-only XML contexts."""

import time
import xml.etree.ElementTree as ET

from crossing_audit import uncertainty_reason
from import_roads import tags
from maneuver_graph import replay
from targeted_evidence import PORT, SOURCE_NODES, selected_incidence
from xml_stream import parse_xml


def source_examples(source, output, graph, audit, measurements=None, observe=None):
    """Retain original node/incident-way tags and directed, history-aware transition evidence."""
    previous = time.perf_counter()

    def mark(stage):
        nonlocal previous
        now = time.perf_counter()
        if measurements is not None:
            measurements.setdefault("phaseMs", {})[stage] = (now - previous) * 1000
        if observe: observe(stage)
        previous = time.perf_counter()

    incoming, outgoing, stats = selected_incidence(graph.base.roads, SOURCE_NODES)
    if measurements is not None: measurements["index"] = stats
    mark("sourceIndexes")
    selected = {row["id"]: row for row in audit["barrierPolicy"]["decisions"] if row["id"] in SOURCE_NODES}
    if set(selected) != SOURCE_NODES: raise ValueError("A source-backed barrier fixture is missing")
    for node, decision in selected.items():
        decision["incomingRoadIds"] = [graph.base.roads[index]["id"] for index in incoming[node]]
        decision["outgoingRoadIds"] = [graph.base.roads[index]["id"] for index in outgoing[node]]
        decision["transitions"] = [{"fromRoadId": graph.base.roads[left]["id"], "toRoadId": graph.base.roads[right]["id"],
                                    **replay(graph, [left, right])} for left in incoming[node] for right in outgoing[node]]
        if decision["blockedByModel"] and any(row["allowed"] for row in decision["transitions"]):
            raise ValueError("Closed source-backed barrier has a through transition")
    port = selected[PORT]
    if not port["open"] or port["blockedByModel"] or not any(row["allowed"] for row in port["transitions"]):
        raise ValueError("Explicit car permission did not admit the real port transition")
    mark("sourceTransitions")
    node_ids, ways = set(SOURCE_NODES), []
    with parse_xml(source, events=("start", "end")) as parser:
        _, root = next(parser)
        for event, element in parser:
            if event == "end" and element.tag in {"node", "way", "relation"}:
                if element.tag == "way":
                    refs = {int(node.get("ref")) for node in element.findall("nd")}
                    matches = refs.intersection(SOURCE_NODES)
                    if matches:
                        ways.append(ET.tostring(element))
                        node_ids.update(refs)
                        for node in matches:
                            selected[node].setdefault("sourceWays", []).append({"id": int(element.get("id")), "tags": tags(element)})
                root.remove(element)
    mark("sourceWayScan")
    with output.open("wb") as target:
        target.write(b'<osm version="0.6">\n')
        with parse_xml(source, events=("start", "end")) as parser:
            _, root = next(parser)
            for event, element in parser:
                if event == "end" and element.tag in {"node", "way", "relation"}:
                    if element.tag == "node" and int(element.get("id")) in node_ids: target.write(ET.tostring(element))
                    root.remove(element)
        mark("sourceNodeScan")
        for way in ways: target.write(way)
        target.write(b'</osm>\n')
    mark("sourceExcerpt")
    return list(selected.values()), incoming[PORT], outgoing[PORT]


def source_uncertainties(source, destination):
    """Keep complete original uncertain ways and referenced nodes in a small excerpt."""
    selected, way_xml, node_ids = [], [], set()
    with parse_xml(source, events=("start", "end")) as parser:
        _, root = next(parser)
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
        with parse_xml(source, events=("start", "end")) as parser:
            _, root = next(parser)
            for event, element in parser:
                if event == "end" and element.tag in {"node", "way", "relation"}:
                    if element.tag == "node" and int(element.get("id")) in node_ids: stream.write(ET.tostring(element))
                    root.remove(element)
        for element in way_xml: stream.write(element)
        stream.write(b'</osm>\n')
    return selected
