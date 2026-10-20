"""Versioned source-import binding for compact outgoing-road storage."""

from collections import Counter
import math
import time
from input_storage import Nodes, WayNodes, read_osm

from compact_storage import Roads, build_maneuver_graph, digest
from source_outgoing import build_graph
from barrier_policy import MODEL_ID, prepare_barriers
from import_maneuvers import candidate
from import_roads import DEFAULT_SPEEDS, TURN_KINDS, access_allowed, distance_m, inside, speed_kph, tags


def build_base(nodes, ways, relations, bounds, model, omitted_relations=(), id_mode="ordered", measurements=None, observe=None):
    audit = {"unsupportedRestrictions": [], "appliedRestrictions": [], "excludedWays": [], "ignoredNonCarRestrictions": []}
    excluded, closed_nodes = set(), set()
    restrictions = []
    for relation in relations:
        if int(relation.get("id")) in omitted_relations: continue
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
    roads, cut_nodes, blocked_nodes = Roads(), set(), set(closed_nodes)
    excluded_reasons = Counter()
    for node_id, node in nodes.items():
        props = node["tags"]
        if props.get("barrier") or not access_allowed(props) or any(k.endswith(":conditional") for k in props):
            blocked_nodes.add(node_id)
    for way_id in sorted(ways):
        way = ways[way_id]
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
    graph = build_graph(roads, restrictions, blocked_nodes, delays, model["uTurnDelayMs"], id_mode, measurements, observe, node_ids=nodes.ids if type(nodes) is Nodes and nodes.ordered and nodes.index is None else None)
    used_restrictions = {r for t in graph.blocked_turns for r in t["restrictionIds"]}
    audit["appliedRestrictions"] = [r for r in restrictions if r["id"] in used_restrictions]
    audit["inactiveSupportedRestrictions"] = [r["id"] for r in restrictions if r["id"] not in used_restrictions]
    audit.update({"sourceNodes": len(nodes), "sourceWays": len(ways), "excludedWayCounts": dict(excluded_reasons),
                  "cutExitNodes": sorted(cut_nodes), "blockedNodes": sorted(blocked_nodes),
                  "onewayFourthAvenueSourceTags": ways.get(5987900, {}).get("tags"),
                  "onewayFourthAvenue": [{"id": e["id"], "from": e["from"], "to": e["to"]} for e in roads if e["way"] == 5987900]})
    return graph, audit

