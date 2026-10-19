"""Extend the frozen v1 importer without changing its costs or fallback policy."""

from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from import_roads import import_roads, tags
from maneuver_graph import build_maneuver_graph


PROHIBITED = {"no_left_turn", "no_right_turn", "no_straight_on", "no_u_turn"}


def candidate(relation):
    props = tags(relation)
    if any(key.endswith(":conditional") for key in props):
        raise ValueError("conditional restriction")
    kind = next((props[key] for key in ("restriction:motorcar", "restriction:motor_vehicle", "restriction:vehicle", "restriction") if key in props), None)
    if kind not in PROHIBITED:
        raise ValueError("unsupported via-way restriction kind")
    members = [(member.get("role"), member.get("type"), int(member.get("ref"))) for member in relation.findall("member")]
    froms = [ref for role, typ, ref in members if role == "from" and typ == "way"]
    tos = [ref for role, typ, ref in members if role == "to" and typ == "way"]
    vias = [ref for role, typ, ref in members if role == "via" and typ == "way"]
    if len(froms) != 1 or len(tos) != 1 or not vias or len(members) != len(vias) + 2:
        raise ValueError("unsupported member roles/counts")
    sequence = froms + vias + tos
    if len(set(sequence)) != len(sequence):
        raise ValueError("repeated/same-way members")
    return {"id": int(relation.get("id")), "kind": kind, "ways": sequence, "tags": props,
            "sourceMembers": [{"role": role, "type": typ, "ref": ref} for role, typ, ref in members]}


def resolve(rule, ways, base):
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
    lookup = {(road["way"], road["from"], road["to"]): index for index, road in enumerate(base.roads)}
    if len(lookup) != len(base.roads):
        raise ValueError("Duplicate directed road geometry")
    if any(triple not in lookup for triple in triples):
        raise ValueError("directed member segment absent after access/coverage/fallback exclusions")
    roads = [lookup[triple] for triple in triples]
    if any(not any(target == right for target, _ in base.adjacency[left]) for left, right in zip(roads, roads[1:])):
        raise ValueError("member path blocked by existing node/access rules")
    return {**rule, "roads": roads, "roadIds": [base.roads[index]["id"] for index in roads], "joinNodes": joins}


def import_maneuvers(path, bounds, model):
    original, original_audit = import_roads(path, bounds, model)
    root = ET.parse(path).getroot()
    ways = {int(way.get("id")): [int(node.get("ref")) for node in way.findall("nd")] for way in root.findall("way")}
    relations = {int(relation.get("id")): relation for relation in root.findall("relation")}
    candidates, reasons = {}, {}
    # v1 has already resolved car modes, exceptions, geographic relevance and unsafe fallbacks.
    for unsupported in original_audit["unsupportedRestrictions"]:
        relation = relations[unsupported["id"]]
        if not any(member.get("role") == "via" and member.get("type") == "way" for member in relation.findall("member")):
            continue
        try:
            rule = candidate(relation)
            candidates[rule["id"]] = rule
        except ValueError as error:
            reasons[unsupported["id"]] = str(error)
    iterations = 0
    with tempfile.TemporaryDirectory() as temporary:
        filtered = Path(temporary) / "roads.osm"
        while True:
            iterations += 1
            revised = ET.Element(root.tag, root.attrib)
            revised.extend(child for child in root if child.tag != "relation" or int(child.get("id")) not in candidates)
            ET.ElementTree(revised).write(filtered, encoding="utf-8", xml_declaration=True)
            base, audit = import_roads(filtered, bounds, model)
            patterns, failed = [], []
            for rule in candidates.values():
                try:
                    patterns.append(resolve(rule, ways, base))
                except ValueError as error:
                    reasons[rule["id"]] = str(error)
                    failed.append(rule["id"])
            if not failed:
                break
            # Reinstating a closure can invalidate another candidate; converge by only removing candidates.
            for relation_id in failed:
                del candidates[relation_id]
    graph = build_maneuver_graph(base, patterns)
    before = {road["id"] for road in original.roads}
    restored = [road for road in base.roads if road["id"] not in before]
    audit.update({"previousGraphIdentity": original.identity, "previousRoads": len(original.roads),
                  "previousUnsupportedRestrictions": len(original_audit["unsupportedRestrictions"]),
                  "viaWayRestrictions": patterns, "viaWayFallbackReasons": [{"id": key, "reason": value} for key, value in sorted(reasons.items())],
                  "fallbackIterations": iterations, "restoredWayIds": sorted({road["way"] for road in restored}),
                  "restoredDirectedRoadIds": [road["id"] for road in restored],
                  "conditionalPolicy": "No date/time evaluation; retain v1 conservative member-road/node and conditional-way closures."})
    return graph, audit
