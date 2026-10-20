"""Versioned importer with member-scoped geometry ambiguity and unchanged car access/costs."""

import time

from barrier_policy import MODEL_ID
from cache_input import prepare_barriers, read_osm
from compact_storage import build_maneuver_graph, digest
from import_maneuvers import candidate
from source_outgoing_input import build_base
from scoped_member_lookup import POLICY_ID, resolve, road_lookup
from input_storage import WayNodes
from road_keys import RoadKeys


def import_maneuvers(path, bounds, model, measurements=None, observe=None, id_mode="ordered"):
    if model.get("restrictionGeometryPolicy") != POLICY_ID: raise ValueError("Require the versioned restriction-geometry policy")
    started = time.perf_counter()
    nodes, ways, relations = read_osm(path)
    parsed = time.perf_counter()
    if measurements is not None:
        measurements["inputStorage"] = {"nodes": nodes.storage_summary(), "ways": ways.storage_summary(), "relations": len(relations)}
    if observe: observe("parsed")
    base_profiles = []

    def build(label, omitted=()):
        profile = {"build": label}
        callback = (lambda stage: observe(f"{label}:{stage}")) if observe else None
        result = build_base(nodes, ways, relations, bounds, model, omitted, id_mode, profile, callback)
        base_profiles.append(profile)
        return result

    original, original_audit = build("original")
    before = RoadKeys(original.roads)
    if measurements is not None: measurements["originalRoadKeys"] = before.summary()
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
    way_nodes = WayNodes(ways)
    iterations = lookups = 0
    lookup_stats = []
    while True:
        iterations += 1
        base, audit = build(f"pass{iterations}", candidates)
        if observe: observe(f"baseReady{iterations}")
        lookup, duplicate_geometry = {}, set()
        if candidates:
            members = {way for rule in candidates.values() for way in rule["ways"]}
            lookup, duplicate_geometry, stats = road_lookup(base, members)
            lookup_stats.append({"iteration": iterations, **stats})
        if observe: observe(f"lookupReady{iterations}")
        lookups += bool(candidates)
        patterns, failed = [], []
        for rule in candidates.values():
            try:
                patterns.append(resolve(rule, way_nodes, base, lookup, duplicate_geometry))
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
    graph.identity = digest({"restrictionGeometryPolicy": POLICY_ID, "graphIdentity": graph.identity})
    if observe: observe("historyBuilt")
    restored = before.restored(base.roads)
    del before
    audit.update({"previousGraphIdentity": previous_id, "previousRoads": previous_roads,
                  "previousUnsupportedRestrictions": len(original_audit["unsupportedRestrictions"]),
                  "viaWayRestrictions": patterns, "viaWayFallbackReasons": [{"id": key, "reason": value} for key, value in sorted(reasons.items())],
                  "fallbackIterations": iterations, "restoredWayIds": sorted({road["way"] for road in restored}),
                  "restoredDirectedRoadIds": [road["id"] for road in restored],
                  "conditionalPolicy": "No date/time evaluation; retain v1 conservative member-road/node and conditional-way closures."})
    if measurements is not None:
        measurements.update({"parseMs": (parsed - started) * 1000, "baseAndRestrictionsMs": (base_done - parsed) * 1000,
                             "historyMs": (time.perf_counter() - base_done) * 1000, "baseBuilds": iterations + 1,
                             "baseGraphProfiles": base_profiles, "sharedRoadLookupBuilds": lookups, "memberRoadLookups": lookup_stats, "resolvedViaWayRules": len(patterns), "xmlPasses": 1})
    return graph, audit


def import_barriers(source, prepared, bounds, model, measurements=None, observe=None, id_mode="ordered"):
    if model.get("id") != MODEL_ID: raise ValueError("Barrier semantics require the v3 model identity")
    policy = prepare_barriers(source, prepared, bounds)
    graph, audit = import_maneuvers(prepared, bounds, model, measurements, observe, id_mode)
    blocked = set(audit["blockedNodes"])
    for decision in policy["decisions"]:
        decision["blockedByModel"] = decision["id"] in blocked
        if not decision["open"] and not decision["blockedByModel"]: raise ValueError("Conservative barrier closure was lost")
    audit["barrierPolicy"] = policy
    graph.identity = digest({"model": MODEL_ID, "baseIdentity": graph.base.identity,
                             "patterns": graph.patterns, "states": graph.states, "transitions": graph.adjacency, "restrictionGeometryPolicy": POLICY_ID})
    return graph, audit

