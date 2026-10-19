"""Small source-backed parity/oracle fixtures for the versioned member importer."""

import gzip
import hashlib
import math
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from barrier_policy import MODEL_ID
from barrier_policy_test import xml as barrier_xml
from cache_import import import_barriers as frozen_barriers, import_maneuvers as frozen_maneuvers
from compact_storage import encoded_blocks
from import_capacity import graph_data
from maneuver_graph import replay
from maneuver_graph_test import MODEL, osm
from member_import import import_barriers, import_maneuvers
from native_support import pack_graph
from state_graph import bellman_ford, dijkstra


DUPLICATE = '<way id="50"><nd ref="5"/><nd ref="6"/><nd ref="5"/><nd ref="6"/><tag k="highway" v="residential"/></way>'
CHAINED = '<relation id="100"><member type="way" role="from" ref="20"/><member type="node" role="via" ref="4"/><member type="way" role="to" ref="30"/><tag k="type" v="restriction"/><tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/></relation>'


def cases():
    reversed_via = ET.fromstring(osm())
    via = next(way for way in reversed_via.findall("way") if way.get("id") == "20")
    for element, ref in zip(via.findall("nd"), (4, 3, 2)): element.set("ref", str(ref))
    via.find("tag[@k='oneway']").set("v", "-1")
    yield "supported", osm(), False
    yield "only", osm("only_straight_on"), False
    yield "conditional", osm(extra='<tag k="restriction:conditional" v="no_left_turn @ (Mo-Fr)"/>'), False
    yield "ambiguous", osm(from_nodes=(1, 2, 3)), False
    yield "motorcar-exception", osm(extra='<tag k="except" v="motorcar"/>'), False
    yield "bicycle", osm().replace('type" v="restriction"', 'type" v="restriction:bicycle"'), False
    yield "unselected-duplicate", osm().replace('</osm>', DUPLICATE + '</osm>'), False
    yield "ambiguous-before-duplicate", osm(from_nodes=(1, 2, 3)).replace('</osm>', DUPLICATE + '</osm>'), False
    yield "selected-duplicate", osm(from_nodes=(1, 2, 1, 2)), False
    yield "chained-closure", osm().replace('</osm>', CHAINED + '</osm>'), False
    yield "reversed-via", ET.tostring(reversed_via, encoding="unicode"), False
    yield "no-restrictions", osm().split('<relation')[0] + '</osm>', False
    for name, props in (
        ("explicit-border", {"barrier": "border_control", "motorcar": "yes"}),
        ("private-gate", {"barrier": "gate", "access": "private"}),
        ("permissive-gate", {"barrier": "gate", "access": "permissive"}),
        ("motorcar-no", {"barrier": "gate", "motorcar": "no", "access": "yes"}),
        ("conditional-gate", {"barrier": "gate", "motorcar": "yes", "access:conditional": "no @ (Su)"}),
    ): yield name, barrier_xml(props), True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compare(directory, name, source, barriers):
    path = directory / "source.osm"
    path.write_text(source)
    model = {**MODEL, "id": MODEL_ID} if barriers else MODEL
    measurements = {}
    if barriers:
        actual, audit = import_barriers(path, directory / "new.osm", [-1, -1, 1, 1], model, measurements)
        expected, old_audit = frozen_barriers(path, directory / "old.osm", [-1, -1, 1, 1], model)
        assert (directory / "new.osm").read_bytes() == (directory / "old.osm").read_bytes()
        (directory / "new.osm").unlink(); (directory / "old.osm").unlink()
    else:
        actual, audit = import_maneuvers(path, [-1, -1, 1, 1], model, measurements)
        expected, old_audit = frozen_maneuvers(path, [-1, -1, 1, 1], model)
    assert audit == old_audit and actual.identity == expected.identity, name
    canonical = b"".join(encoded_blocks(graph_data(actual, model)))
    assert canonical == b"".join(encoded_blocks(graph_data(expected, model))), name
    packed = pack_graph(actual.adjacency, actual.identity)
    old_packed = pack_graph(expected.adjacency, expected.identity)
    assert packed == old_packed and gzip.compress(packed, mtime=0) == gzip.compress(old_packed, mtime=0), name
    full = bounded = 0
    for state in range(len(actual.states)):
        oracle = bellman_ford(expected.adjacency, [(state, 1)])
        assert dijkstra(actual.adjacency, [(state, 1)]).labels == oracle, name
        full += len(oracle)
        for budget in (0, 10_000, 100_000):
            assert dijkstra(actual.adjacency, [(state, 1)], budget).labels == [cost if cost <= budget else math.inf for cost in oracle], name
            bounded += len(oracle)
    for rule in actual.patterns:
        assert not replay(actual, rule["roads"])["allowed"], name
    reasons = audit["viaWayFallbackReasons"]
    if name == "unselected-duplicate":
        assert reasons == [{"id": 99, "reason": "Duplicate directed road geometry"}]
        assert audit["fallbackIterations"] == 2 and not actual.patterns
        assert measurements["memberRoadLookups"][0]["duplicateRoads"] > 0
    if name == "ambiguous-before-duplicate":
        assert reasons == [{"id": 99, "reason": "ambiguous/disconnected member join"}]
    if name == "selected-duplicate":
        assert reasons == [{"id": 99, "reason": "missing, closed or repeated-node member way"}]
    return {"name": name, "sourceSha256": sha(source.encode()), "graphIdentity": actual.identity,
            "canonicalSha256": sha(canonical), "csrSha256": sha(packed), "auditSha256": sha(b"".join(encoded_blocks(audit))),
            "states": len(actual.states), "fallbackIterations": audit["fallbackIterations"], "fallbackReasons": reasons,
            "fullCostComparisons": full, "boundedCostComparisons": bounded, "prohibitionReplays": len(actual.patterns),
            "lookupPasses": measurements["sharedRoadLookupBuilds"], "identicalBarrierSource": barriers}


def qualify():
    with tempfile.TemporaryDirectory() as temporary:
        results = [compare(Path(temporary), *row) for row in cases()]
    return {"cases": results, "caseCount": len(results),
            "fullCostComparisons": sum(row["fullCostComparisons"] for row in results),
            "boundedCostComparisons": sum(row["boundedCostComparisons"] for row in results),
            "scope": "Fresh synthetic OSM-tag fixtures, exact frozen importer graph/audit/CSR/gzip/barrier bytes, all-state Bellman-Ford full/bounded comparisons and prohibition replay. No new regional qualification."}
