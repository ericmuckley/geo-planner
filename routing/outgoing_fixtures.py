"""Fresh frozen-importer fixture parity for compact outgoing-road storage."""

import gzip
import hashlib
import math
from pathlib import Path
import tempfile

from barrier_policy import MODEL_ID
from member_import import import_barriers as frozen_barriers, import_maneuvers as frozen_maneuvers
from compact_storage import encoded_blocks
from import_capacity import graph_data
from maneuver_graph import replay
from maneuver_graph_test import MODEL
from member_fixtures import cases
from outgoing_import import import_barriers, import_maneuvers
from native_support import pack_graph
from state_graph import bellman_ford, dijkstra


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compare(directory, name, source, barriers, id_mode):
    path = directory / "source.osm"
    path.write_text(source)
    model = {**MODEL, "id": MODEL_ID} if barriers else MODEL
    measurements = {}
    if barriers:
        actual, audit = import_barriers(path, directory / "new.osm", [-1, -1, 1, 1], model, measurements, id_mode=id_mode)
        expected, old_audit = frozen_barriers(path, directory / "old.osm", [-1, -1, 1, 1], model)
        assert (directory / "new.osm").read_bytes() == (directory / "old.osm").read_bytes()
        (directory / "new.osm").unlink(); (directory / "old.osm").unlink()
    else:
        actual, audit = import_maneuvers(path, [-1, -1, 1, 1], model, measurements, id_mode=id_mode)
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


def qualify(id_mode="ordered"):
    with tempfile.TemporaryDirectory() as temporary:
        results = [compare(Path(temporary), *row, id_mode) for row in cases()]
    return {"idMode": id_mode, "cases": results, "caseCount": len(results),
            "fullCostComparisons": sum(row["fullCostComparisons"] for row in results),
            "boundedCostComparisons": sum(row["boundedCostComparisons"] for row in results),
            "scope": "Fresh synthetic OSM-tag fixtures, exact frozen importer graph/audit/CSR/gzip/barrier bytes, all-state Bellman-Ford full/bounded comparisons and prohibition replay. No new regional qualification."}
