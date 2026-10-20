"""Explicit semantics and independent costs for scoped duplicate-geometry handling."""

import hashlib
import math
from pathlib import Path
import tempfile

from barrier_policy import MODEL_ID
from compact_storage import encoded_blocks
from import_capacity import graph_data
from member_fixtures import cases
from maneuver_graph import replay
from maneuver_graph_test import MODEL
from outgoing_import import import_barriers as old_barriers, import_maneuvers as old_maneuvers
from scoped_import import import_barriers, import_maneuvers
from scoped_member_lookup import POLICY_ID
from state_graph import bellman_ford, dijkstra


def canonical_hash(data):
    digest = hashlib.sha256()
    for block in encoded_blocks(data): digest.update(block)
    return digest.hexdigest()


def qualify():
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for name, xml, barriers in cases():
            source = directory / "source.osm"
            source.write_text(xml)
            old_model = {**MODEL, "id": MODEL_ID} if barriers else MODEL
            model = {**old_model, "restrictionGeometryPolicy": POLICY_ID}
            if barriers:
                graph, audit = import_barriers(source, directory / "new.osm", [-1, -1, 1, 1], model)
                old, old_audit = old_barriers(source, directory / "old.osm", [-1, -1, 1, 1], old_model)
                assert (directory / "new.osm").read_bytes() == (directory / "old.osm").read_bytes()
            else:
                graph, audit = import_maneuvers(source, [-1, -1, 1, 1], model)
                old, old_audit = old_maneuvers(source, [-1, -1, 1, 1], old_model)
            unchanged = name != "unselected-duplicate"
            if unchanged:
                normalized = graph_data(graph, old_model)
                normalized["graphIdentity"] = old.identity
                assert canonical_hash(normalized) == canonical_hash(graph_data(old, old_model)), name
                assert audit == old_audit, name
            else:
                assert len(graph.patterns) == 1 and not old.patterns
                assert audit["viaWayFallbackReasons"] == []
                assert old_audit["viaWayFallbackReasons"] == [{"id": 99, "reason": "Duplicate directed road geometry"}]
            full = bounded = 0
            for state in range(len(graph.states)):
                exact = bellman_ford(graph.adjacency, [(state, 1)])
                assert dijkstra(graph.adjacency, [(state, 1)]).labels == exact, name
                full += len(exact)
                for budget in (0, 10000, 100000):
                    assert dijkstra(graph.adjacency, [(state, 1)], budget).labels == [cost if cost <= budget else math.inf for cost in exact], name
                    bounded += len(exact)
            for rule in graph.patterns: assert not replay(graph, rule["roads"])["allowed"], name
            results.append({"name": name, "sourceSha256": hashlib.sha256(xml.encode()).hexdigest(),
                            "graphIdentity": graph.identity, "unchangedAfterIdentityNormalization": unchanged,
                            "fullCostComparisons": full, "boundedCostComparisons": bounded,
                            "prohibitionReplays": len(graph.patterns), "fallbackReasons": audit["viaWayFallbackReasons"]})
    return {"policy": POLICY_ID, "caseCount": len(results), "cases": results,
            "fullCostComparisons": sum(row["fullCostComparisons"] for row in results),
            "boundedCostComparisons": sum(row["boundedCostComparisons"] for row in results)}
