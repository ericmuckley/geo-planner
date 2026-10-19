"""Versioned importer: numeric road-key lifetimes; frozen routing rules reused."""

import time

from barrier_policy import MODEL_ID, prepare_barriers
from compact_storage import build_maneuver_graph, digest
from import_maneuvers import candidate
from input_import import build_base, resolve, road_lookup
from input_storage import WayNodes, read_osm
from road_keys import RoadKeys


def import_maneuvers(path, bounds, model, measurements=None, observe=None):
    started = time.perf_counter()
    nodes, ways, relations = read_osm(path)
    parsed = time.perf_counter()
    if measurements is not None:
        measurements["inputStorage"] = {"nodes": nodes.storage_summary(), "ways": ways.storage_summary(), "relations": len(relations)}
    if observe: observe("parsed")
    original, original_audit = build_base(nodes, ways, relations, bounds, model)
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
    while True:
        iterations += 1
        base, audit = build_base(nodes, ways, relations, bounds, model, candidates)
        if observe: observe(f"baseReady{iterations}")
        lookup = road_lookup(base) if candidates else {}
        if observe: observe(f"lookupReady{iterations}")
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

