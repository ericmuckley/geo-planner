"""Versioned, deliberately conservative car access at OSM control-point nodes."""

from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

from anchors import digest
from import_maneuvers import import_maneuvers
from import_roads import ALLOWED_ACCESS, CAR_KEYS, inside, tags


MODEL_ID = "exploratory-static-car-v3"
POLICY_ID = "explicit-control-point-car-v1"
CONTROL_POINTS = {"gate", "lift_gate", "border_control", "toll_booth"}


def barrier_decision(properties):
    """A permission admits static through travel, without claiming current availability."""
    key = next((key for key in CAR_KEYS if key in properties), None)
    result = {"open": False, "accessKey": key, "accessValue": properties.get(key)}
    if properties.get("barrier") not in CONTROL_POINTS:
        reason = "unsupported-barrier"
    elif any(key.endswith(":conditional") for key in properties):
        reason = "conditional"
    elif any(key.startswith(("oneway", "reversible", "restriction")) or
             any(key.startswith(f"{mode}:") for mode in CAR_KEYS) for key in properties):
        reason = "unsupported-access-qualifier"
    elif any(key.startswith(("maxwidth", "maxheight", "maxlength", "maxweight", "maxaxleload")) or
             key in {"width", "height"} for key in properties):
        reason = "unmodeled-dimensions"
    elif properties.get("locked", "no") != "no":
        reason = "locked-or-unknown"
    elif properties.get("opening_hours", "24/7") != "24/7":
        reason = "unmodeled-opening-hours"
    elif key is None:
        reason = "missing-explicit-car-access"
    elif properties[key] not in ALLOWED_ACCESS or (key == "access" and properties[key] == "designated"):
        reason = "car-access-not-permitted"
    else:
        result["open"] = True
        reason = "explicit-car-permission"
    return {**result, "reason": reason}


def prepare_barriers(source, destination, bounds):
    """Stream one top-level OSM object at a time; preserve all but qualified barrier tags."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Barrier preparation requires a separate output file")
    records, counts = [], Counter()
    parser = ET.iterparse(source, events=("start", "end"))
    _, root = next(parser)
    if root.tag != "osm": raise ValueError("Expected an OSM XML document")
    depth = 1
    with destination.open("wb") as output:
        attributes = ''.join(f" {key}={quoteattr(value)}" for key, value in root.attrib.items())
        output.write(f'<?xml version="1.0" encoding="utf-8"?>\n<osm{attributes}>\n'.encode())
        for event, element in parser:
            if event == "start":
                depth += 1
                continue
            if depth == 2:
                if element.tag == "node":
                    properties = tags(element)
                    if properties.get("barrier"):
                        point = [float(element.get("lon")), float(element.get("lat"))]
                        decision = barrier_decision(properties)
                        if not inside(point, bounds): decision = {**decision, "open": False, "reason": "outside-bounds"}
                        records.append({"id": int(element.get("id")), "point": point, "tags": properties, **decision})
                        counts[decision["reason"]] += 1
                        if decision["open"]:
                            for tag in list(element.findall("tag")):
                                if tag.get("k") == "barrier": element.remove(tag)
                output.write(ET.tostring(element, encoding="utf-8"))
                root.remove(element)
            depth -= 1
        output.write(b"</osm>\n")
    return {"id": POLICY_ID, "decisions": records, "decisionCounts": dict(counts),
            "delayPolicy": "No barrier delay, queue, citizenship, documents or current operating-state evaluation; static permission only."}


def import_barriers(source, prepared, bounds, model):
    if model.get("id") != MODEL_ID: raise ValueError("Barrier semantics require the v3 model identity")
    policy = prepare_barriers(source, prepared, bounds)
    graph, audit = import_maneuvers(prepared, bounds, model)
    blocked = set(audit["blockedNodes"])
    for decision in policy["decisions"]:
        decision["blockedByModel"] = decision["id"] in blocked
        if not decision["open"] and not decision["blockedByModel"]:
            raise ValueError("Conservative barrier closure was lost")
    audit["barrierPolicy"] = policy
    # The unchanged v2 builder compiles turn history; the wrapper owns the new semantic identity.
    graph.identity = digest({"model": MODEL_ID, "baseIdentity": graph.base.identity,
                             "patterns": graph.patterns, "states": graph.states, "transitions": graph.adjacency})
    return graph, audit
