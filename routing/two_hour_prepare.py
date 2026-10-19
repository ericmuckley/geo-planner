"""Complete original references and qualify the paged selector against six frozen fixtures."""

from anchors import digest, file_hash
from compact_storage import encoded_blocks
from import_capacity import graph_data
from input_import import import_barriers
from paged_select import select_ids
from staged_prepare import command


def artifact(path): return {"bytes": path.stat().st_size, "sha256": file_hash(path)}


def prepare(source, bounds, output, monitor=None):
    output.mkdir(exist_ok=True, parents=True)
    ids = output / "selected-ids.txt"
    selection = select_ids(source, bounds, ids, monitor.checkpoint if monitor else None)
    if monitor: monitor.checkpoint("selected")
    xml = output / "car-roads.osm"
    commands = {"completeReferences": command(["osmium", "getid", "--add-referenced", "--id-file", str(ids), str(source), "-f", "osm", "-o", str(xml)], output, "completeReferences", monitor),
                "checkReferences": command(["osmium", "check-refs", "--check-relations", str(xml)], output, "checkReferences", monitor)}
    return xml, selection, commands


def fixtures(inputs, output):
    rows = []
    for index in range(6):
        original = inputs / "coverage-pilot/staged-calibration-v2-r4/fixtures" / str(index)
        target = output / "fixtures" / str(index)
        target.mkdir(parents=True)
        xml, selection, _ = prepare(original / "region.osm.pbf", [-1, -1, 1, 1], target)
        model = {"id": "exploratory-static-car-v3", "signalDelayMs": 5000, "uTurnDelayMs": 20000}
        graph, audit = import_barriers(xml, target / "barrier.osm", [-1, -1, 1, 1], model)
        old_graph, old_audit = import_barriers(original / "old/car-roads.osm", target / "old-barrier.osm", [-1, -1, 1, 1], model)
        if b"".join(encoded_blocks(graph_data(graph, model))) != b"".join(encoded_blocks(graph_data(old_graph, model))) or audit != old_audit:
            raise ValueError(f"Sparse fixture differs: {index}")
        rows.append({"fixture": index, "graphIdentity": graph.identity, "auditSha256": digest(audit), "graphAndAuditIdentical": True,
                     "originalSourceArtifact": artifact(original / "source.osm"), "selection": selection})
    return rows

