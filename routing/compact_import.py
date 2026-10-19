"""Versioned compact representation; frozen streaming importer supplies the rules.

This copy keeps the frozen control flow while substituting arrays/builders and
streamed identity hashes. Real artifact equality gates use on larger inputs.
"""

from collections import Counter
import math
import time
import xml.etree.ElementTree as ET

from compact_storage import Roads, build_graph, build_maneuver_graph, digest
from barrier_policy import MODEL_ID, prepare_barriers
from import_maneuvers import candidate
from import_roads import DEFAULT_SPEEDS, TURN_KINDS, access_allowed, distance_m, inside, speed_kph, tags


def read_osm(path):
    """Keep decoded graph inputs, releasing each XML object after its closing tag."""
    nodes, ways, relations = {}, {}, []
    parser = ET.iterparse(path, events=("start", "end"))
    _, root = next(parser)
    if root.tag != "osm": raise ValueError("Expected an OSM XML document")
    depth = 1
    for event, element in parser:
        if event == "start":
            depth += 1
            continue
        if depth == 2:
            if element.tag == "node":
                nodes[int(element.get("id"))] = {"point": [float(element.get("lon")), float(element.get("lat"))], "tags": tags(element)}
            elif element.tag == "way":
                ways[int(element.get("id"))] = {"nodes": [int(node.get("ref")) for node in element.findall("nd")], "tags": tags(element)}
            elif element.tag == "relation":
                relations.append(element)
            root.remove(element)
        depth -= 1
    return nodes, ways, relations


def build_base(nodes, ways, relations, bounds, model, omitted_relations=()):
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


def road_lookup(base):
    lookup = {(road["way"], road["from"], road["to"]): index for index, road in enumerate(base.roads)}
    return lookup


def resolve(rule, ways, base, lookup):
    members = [ways.get(way, []) for way in rule["ways"]]
    if any(len(nodes) < 2 or len(set(nodes)) != len(nodes) for nodes in members):
        raise ValueError("missing, closed or repeated-node member way")
    joins = []
    for left, right in zip(members, members[1:]):
        shared = set(left).intersection(right)
        if len(shared) != 1:
            raise ValueError("ambiguous/disconnected member join")
        join = next(iter(shared))
        if join not in (left[0], left[-1]) or join not in (right[0], right[-1]):
            raise ValueError("member join is not an endpoint")
        joins.append(join)
    triples = []
    first = members[0]
    triples.append((rule["ways"][0], first[1] if first[0] == joins[0] else first[-2], joins[0]))
    for index, nodes in enumerate(members[1:-1], 1):
        if joins[index - 1] == joins[index]:
            raise ValueError("via way has identical entry and exit")
        directed = nodes if nodes[0] == joins[index - 1] else list(reversed(nodes))
        triples.extend((rule["ways"][index], tail, head) for tail, head in zip(directed, directed[1:]))
    last = members[-1]
    triples.append((rule["ways"][-1], joins[-1], last[1] if last[0] == joins[-1] else last[-2]))
    if len(lookup) != len(base.roads):
        raise ValueError("Duplicate directed road geometry")
    if any(triple not in lookup for triple in triples):
        raise ValueError("directed member segment absent after access/coverage/fallback exclusions")
    roads = [lookup[triple] for triple in triples]
    if any(not any(target == right for target, _ in base.adjacency[left]) for left, right in zip(roads, roads[1:])):
        raise ValueError("member path blocked by existing node/access rules")
    return {**rule, "roads": roads, "roadIds": [base.roads[index]["id"] for index in roads], "joinNodes": joins}


def import_maneuvers(path, bounds, model, measurements=None, observe=None):
    started = time.perf_counter()
    nodes, ways, relations = read_osm(path)
    parsed = time.perf_counter()
    if observe: observe("parsed")
    original, original_audit = build_base(nodes, ways, relations, bounds, model)
    before = {road["id"] for road in original.roads}
    previous_id, previous_roads = original.identity, len(original.roads)
    del original
    if observe: observe("originalBase")
    by_relation = {int(relation.get("id")): relation for relation in relations}
    candidates, reasons = {}, {}
    for unsupported in original_audit["unsupportedRestrictions"]:
        relation = by_relation[unsupported["id"]]
        if not any(member.get("role") == "via" and member.get("type") == "way" for member in relation.findall("member")):
            continue
        try:
            rule = candidate(relation)
            candidates[rule["id"]] = rule
        except ValueError as error:
            reasons[unsupported["id"]] = str(error)
    way_nodes = {way: data["nodes"] for way, data in ways.items()}
    iterations = lookups = 0
    while True:
        iterations += 1
        base, audit = build_base(nodes, ways, relations, bounds, model, candidates)
        lookup = road_lookup(base) if candidates else {}
        lookups += bool(candidates)
        patterns, failed = [], []
        for rule in candidates.values():
            try:
                patterns.append(resolve(rule, way_nodes, base, lookup))
            except ValueError as error:
                reasons[rule["id"]] = str(error)
                failed.append(rule["id"])
        del lookup
        if observe: observe(f"basePass{iterations}")
        if not failed: break
        for relation_id in failed: del candidates[relation_id]
        del base
    del nodes, ways, relations, by_relation, way_nodes
    base_done = time.perf_counter()
    if observe: observe("inputsReleased")
    graph = build_maneuver_graph(base, patterns)
    if observe: observe("historyBuilt")
    restored = [road for road in base.roads if road["id"] not in before]
    audit.update({"previousGraphIdentity": previous_id, "previousRoads": previous_roads,
                  "previousUnsupportedRestrictions": len(original_audit["unsupportedRestrictions"]),
                  "viaWayRestrictions": patterns, "viaWayFallbackReasons": [{"id": key, "reason": value} for key, value in sorted(reasons.items())],
                  "fallbackIterations": iterations, "restoredWayIds": sorted({road["way"] for road in restored}),
                  "restoredDirectedRoadIds": [road["id"] for road in restored],
                  "conditionalPolicy": "No date/time evaluation; retain v1 conservative member-road/node and conditional-way closures."})
    if measurements is not None:
        measurements.update({"parseMs": (parsed - started) * 1000, "baseAndRestrictionsMs": (base_done - parsed) * 1000,
                             "historyMs": (time.perf_counter() - base_done) * 1000, "baseBuilds": iterations + 1,
                             "sharedRoadLookupBuilds": lookups, "resolvedViaWayRules": len(patterns), "xmlPasses": 1})
    return graph, audit


def import_barriers(source, prepared, bounds, model, measurements=None, observe=None):
    if model.get("id") != MODEL_ID: raise ValueError("Barrier semantics require the v3 model identity")
    policy = prepare_barriers(source, prepared, bounds)
    graph, audit = import_maneuvers(prepared, bounds, model, measurements, observe)
    blocked = set(audit["blockedNodes"])
    for decision in policy["decisions"]:
        decision["blockedByModel"] = decision["id"] in blocked
        if not decision["open"] and not decision["blockedByModel"]: raise ValueError("Conservative barrier closure was lost")
    audit["barrierPolicy"] = policy
    graph.identity = digest({"model": MODEL_ID, "baseIdentity": graph.base.identity,
                             "patterns": graph.patterns, "states": graph.states, "transitions": graph.adjacency})
    return graph, audit

