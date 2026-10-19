"""Audited, deliberately limited OSM-to-static-road-model importer."""

from collections import Counter
import math
import re
import xml.etree.ElementTree as ET

from state_graph import build_graph


DEFAULT_SPEEDS = {
    "motorway": 100, "motorway_link": 40, "trunk": 80, "trunk_link": 40,
    "primary": 55, "primary_link": 35, "secondary": 45, "secondary_link": 30,
    "tertiary": 40, "tertiary_link": 30, "unclassified": 35, "residential": 30,
    "living_street": 10, "service": 15,
}
ALLOWED_ACCESS = {"yes", "permissive", "designated"}
CAR_KEYS = ("motorcar", "motor_vehicle", "vehicle", "access")
TURN_KINDS = {"no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn", "no_entry", "no_exit",
              "only_left_turn", "only_right_turn", "only_straight_on", "only_u_turn"}


def tags(element):
    return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}


def inside(point, bounds):
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def distance_m(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(h)))


def speed_kph(value, default):
    if value is None:
        return default
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(mph|km/h|kph)?", value.strip())
    if not match:
        raise ValueError(f"Unsupported maxspeed: {value}")
    speed = float(match[1]) * (1.609344 if match[2] == "mph" else 1)
    if not 0 < speed <= 160:
        raise ValueError(f"Unsupported maxspeed: {value}")
    return speed


def access_allowed(properties, direction=None):
    for key in CAR_KEYS:
        if direction and f"{key}:{direction}" in properties:
            return properties[f"{key}:{direction}"] in ALLOWED_ACCESS
        if key in properties:
            return properties[key] in ALLOWED_ACCESS
    return True


def import_roads(path, bounds, model):
    root = ET.parse(path).getroot()
    nodes = {int(n.get("id")): {"point": [float(n.get("lon")), float(n.get("lat"))], "tags": tags(n)}
             for n in root.findall("node")}
    ways = {int(w.get("id")): {"nodes": [int(n.get("ref")) for n in w.findall("nd")], "tags": tags(w)}
            for w in root.findall("way")}
    audit = {"unsupportedRestrictions": [], "appliedRestrictions": [], "excludedWays": [], "ignoredNonCarRestrictions": []}
    excluded, closed_nodes = set(), set()
    restrictions = []
    for relation in root.findall("relation"):
        properties = tags(relation)
        relation_type = properties.get("type", "")
        if not relation_type.startswith("restriction"):
            continue
        members = [(m.get("role"), m.get("type"), int(m.get("ref"))) for m in relation.findall("member")]
        member_ways = {ref for _, kind, ref in members if kind == "way"}
        # Out-of-area completion can pull in unrelated restrictions.
        node_members = [ref for _, kind, ref in members if kind == "node"]
        if not (any(inside(nodes[n]["point"], bounds) for way in member_ways for n in ways.get(way, {}).get("nodes", []) if n in nodes)
                or any(inside(nodes[n]["point"], bounds) for n in node_members if n in nodes)):
            continue
        relation_id = int(relation.get("id"))
        exceptions = {x.strip() for x in properties.get("except", "").split(";")}
        if exceptions.intersection({"motorcar", "motor_vehicle", "vehicle"}):
            audit["ignoredNonCarRestrictions"].append(relation_id)
            continue
        kind = next((properties[k] for k in ("restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle", "restriction") if k in properties), None)
        mode_type = relation_type.split(":", 1)[-1] if ":" in relation_type else None
        if mode_type and mode_type not in {"motorcar", "motor_vehicle", "vehicle"}:
            audit["ignoredNonCarRestrictions"].append(relation_id)
            continue
        if mode_type and kind is None:
            kind = properties.get("restriction")
        if kind is None and not any(k in properties for k in ("restriction:conditional", "restriction:motorcar:conditional", "restriction:motor_vehicle:conditional", "restriction:vehicle:conditional")):
            if any(k.startswith("restriction:") for k in properties):
                audit["ignoredNonCarRestrictions"].append(relation_id)
                continue
        froms = [ref for role, typ, ref in members if role == "from" and typ == "way"]
        tos = [ref for role, typ, ref in members if role == "to" and typ == "way"]
        via = [ref for role, typ, ref in members if role == "via" and typ == "node"]
        conditional = any(k.startswith("restriction") and k.endswith(":conditional") for k in properties)
        supported = (kind in TURN_KINDS and not conditional and len(froms) == len(tos) == len(via) == 1
                     and len(members) == 3 and (froms[0] != tos[0] or kind.endswith("u_turn") or kind.endswith("straight_on")))
        if not supported:
            if not member_ways and not node_members:
                raise ValueError(f"Cannot conservatively locate unsupported restriction {relation_id}")
            excluded.update(member_ways)
            if not member_ways:
                closed_nodes.update(node_members)
            audit["unsupportedRestrictions"].append({"id": relation_id, "tags": properties, "excludedMemberWays": sorted(member_ways),
                                                      "blockedMemberNodes": sorted(node_members) if not member_ways else []})
            continue
        restrictions.append({"id": relation_id, "kind": kind, "fromWay": froms[0], "toWay": tos[0], "via": via[0]})
    roads, cut_nodes, blocked_nodes = [], set(), set(closed_nodes)
    excluded_reasons = Counter()
    for node_id, node in nodes.items():
        props = node["tags"]
        if props.get("barrier") or not access_allowed(props) or any(k.endswith(":conditional") for k in props):
            blocked_nodes.add(node_id)
    for way_id, way in sorted(ways.items()):
        props = way["tags"]
        highway = props.get("highway")
        if highway not in DEFAULT_SPEEDS:
            continue
        reason = None
        if way_id in excluded:
            reason = "unsupported-restriction-member"
        elif not access_allowed(props):
            reason = "access"
        elif props.get("area") == "yes" or props.get("ford") or props.get("service") in {"driveway", "parking_aisle"}:
            reason = "area-ford-driveway-parking"
        elif any(k.endswith(":conditional") or k.startswith("reversible") or k.startswith("restriction") for k in props):
            reason = "conditional-or-way-restriction"
        elif any(k.endswith(":lanes") or ":lanes:" in k for k in props if k.startswith(("access", "vehicle", "motor", "oneway"))):
            reason = "lane-access"
        oneway = props.get("oneway:motorcar", props.get("oneway:motor_vehicle", props.get("oneway")))
        if oneway is None:
            oneway = "yes" if props.get("junction") in {"roundabout", "circular"} or highway == "motorway" else "no"
        if oneway not in {"yes", "1", "true", "no", "0", "false", "-1"}:
            reason = "unsupported-oneway"
        try:
            forward_speed = speed_kph(props.get("maxspeed:forward", props.get("maxspeed")), DEFAULT_SPEEDS[highway])
            reverse_speed = speed_kph(props.get("maxspeed:backward", props.get("maxspeed")), DEFAULT_SPEEDS[highway])
        except ValueError:
            reason = "unsupported-speed"
        if reason:
            excluded_reasons[reason] += 1
            audit["excludedWays"].append({"id": way_id, "reason": reason})
            continue
        for segment, (tail, head) in enumerate(zip(way["nodes"], way["nodes"][1:])):
            if tail not in nodes or head not in nodes:
                raise ValueError(f"Missing referenced node on way {way_id}")
            a, b = nodes[tail]["point"], nodes[head]["point"]
            if not inside(a, bounds) or not inside(b, bounds):
                cut_nodes.update(n for n in (tail, head) if inside(nodes[n]["point"], bounds))
                continue
            if tail == head:
                continue
            length = distance_m(a, b)
            for start, end, suffix, speed, allowed in (
                (tail, head, "f", forward_speed, oneway != "-1" and access_allowed(props, "forward")),
                (head, tail, "r", reverse_speed, oneway in {"no", "0", "false", "-1"} and access_allowed(props, "backward")),
            ):
                if allowed:
                    roads.append({"id": f"{way_id}:{segment}:{suffix}", "way": way_id, "from": start, "to": end,
                                  "costMs": max(1, math.ceil(length * 3600 / speed)),
                                  "fromPoint": nodes[start]["point"], "toPoint": nodes[end]["point"], "name": props.get("name")})
    if not roads:
        raise ValueError("No supported roads remain")
    delays = {node_id: model["signalDelayMs"] for node_id, node in nodes.items() if node["tags"].get("highway") == "traffic_signals"}
    graph = build_graph(roads, restrictions, blocked_nodes, delays, model["uTurnDelayMs"])
    used_restrictions = {r for t in graph.blocked_turns for r in t["restrictionIds"]}
    audit["appliedRestrictions"] = [r for r in restrictions if r["id"] in used_restrictions]
    audit["inactiveSupportedRestrictions"] = [r["id"] for r in restrictions if r["id"] not in used_restrictions]
    audit.update({"sourceNodes": len(nodes), "sourceWays": len(ways), "excludedWayCounts": dict(excluded_reasons),
                  "cutExitNodes": sorted(cut_nodes), "blockedNodes": sorted(blocked_nodes),
                  "onewayFourthAvenueSourceTags": ways.get(5987900, {}).get("tags"),
                  "onewayFourthAvenue": [{"id": e["id"], "from": e["from"], "to": e["to"]} for e in roads if e["way"] == 5987900]})
    return graph, audit
