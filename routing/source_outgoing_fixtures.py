"""Exact scoped-import fixtures and independent full/bounded/partial costs."""

from fractions import Fraction
import math
from pathlib import Path
import tempfile

from barrier_policy import MODEL_ID
from compact_storage import digest
from import_capacity import graph_data
from maneuver_graph import source_seeds, interior_destination
from maneuver_graph_test import MODEL
from member_fixtures import cases
from native_support import pack_graph
from scoped_import import import_barriers as frozen_barriers, import_maneuvers as frozen_maneuvers
from scoped_member_lookup import POLICY_ID
from source_outgoing_import import import_barriers, import_maneuvers
from state_graph import bellman_ford, dijkstra
from virtual_sink import destination_oracle


def qualify():
    results = []
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        for name, xml, barriers in cases():
            source = directory / "source.osm"
            source.write_text(xml)
            model = {**MODEL, "restrictionGeometryPolicy": POLICY_ID}
            if barriers: model["id"] = MODEL_ID
            measurements = {}
            if barriers:
                graph, audit = import_barriers(source, directory / "new.osm", [-1, -1, 1, 1], model, measurements)
                old, previous = frozen_barriers(source, directory / "old.osm", [-1, -1, 1, 1], model)
                if (directory / "new.osm").read_bytes() != (directory / "old.osm").read_bytes(): raise ValueError(name)
            else:
                graph, audit = import_maneuvers(source, [-1, -1, 1, 1], model, measurements)
                old, previous = frozen_maneuvers(source, [-1, -1, 1, 1], model)
            canonical = digest(graph_data(graph, model))
            if audit != previous or canonical != digest(graph_data(old, model)) or pack_graph(graph.adjacency, graph.identity) != pack_graph(old.adjacency, old.identity):
                raise ValueError(f"Scoped fixture differs: {name}")
            full = bounded = partial = 0
            for state in range(len(graph.states)):
                oracle = bellman_ford(old.adjacency, [(state, 1)])
                if dijkstra(graph.adjacency, [(state, 1)]).labels != oracle: raise ValueError(name)
                full += len(oracle)
                for budget in (0, 10000, 100000):
                    if dijkstra(graph.adjacency, [(state, 1)], budget).labels != [value if value <= budget else math.inf for value in oracle]: raise ValueError(name)
                    bounded += len(oracle)
            for road in range(len(graph.base.roads)):
                starts = [(road, Fraction(1, 2))]
                seeds = source_seeds(graph, starts)
                labels = dijkstra(graph.adjacency, seeds).labels
                for destination in range(len(graph.base.roads)):
                    actual = interior_destination(graph, labels, destination, Fraction(3, 4), starts)
                    expected = destination_oracle(old, source_seeds(old, starts), destination, Fraction(3, 4), starts)
                    if actual != expected: raise ValueError(f"Partial fixture differs: {name}")
                    partial += 1
            results.append({"name": name, "graphIdentity": graph.identity, "canonicalSha256": canonical,
                            "fullCostComparisons": full, "boundedCostComparisons": bounded, "partialComparisons": partial,
                            "sourceSortedBuilds": sum(row.get("outgoingMode") == "source-sorted" for row in measurements["baseGraphProfiles"])})
    return {"cases": results, "caseCount": len(results), "fullCostComparisons": sum(row["fullCostComparisons"] for row in results),
            "boundedCostComparisons": sum(row["boundedCostComparisons"] for row in results),
            "partialComparisons": sum(row["partialComparisons"] for row in results),
            "scope": "Fresh scoped restriction/barrier fixtures with identical graph/audit/CSR bytes and independent Bellman-Ford full/bounded/partial costs. Regional proof reuse still requires exact regional artifacts."}
