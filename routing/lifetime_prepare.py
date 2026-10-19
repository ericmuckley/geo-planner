"""Preserve original selection/references with explicit phase and output lifetimes."""

import json
import os
from pathlib import Path
import sys

from anchors import digest, load_json
from compact_storage import encoded_blocks
from import_capacity import graph_data
from input_import import import_barriers
from lifetime_io import copy_advised, partition_ids, stream_command
from paged_io import artifact
from staged_prepare import command


def prepare(source, bounds, output, monitor=None, batches=1):
    output.mkdir(exist_ok=True, parents=True)
    ids, stats, xml = (output / name for name in ("selected-ids.txt", "selection-summary.json", "car-roads.osm"))
    commands = {"selectorProcess": command([sys.executable, "-u", "-B", str(Path(__file__).with_name("selection_process.py")),
        "--source", str(source), "--bounds", json.dumps(bounds), "--ids", str(ids), "--stats", str(stats),
        "--progress", str(output / "selection-progress")], output, "selectorProcess", monitor)}
    selected = load_json(stats)
    if selected["pid"] == os.getpid(): raise ValueError("Selector must exit as a separate process")
    selection = {**selected["selection"], "processLifetime": {"selectorPid": selected["pid"], "parentPid": os.getpid(), "selectorExitedBeforeCompletion": True}}
    if monitor: monitor.checkpoint("selectorExited")
    if batches == 1:
        commands["completeReferences"] = command(["osmium", "getid", "--add-referenced", "--id-file", str(ids), str(source), "-f", "osm", "-o", str(xml)], output, "completeReferences", monitor)
    else:
        parts = []
        for index, id_file in enumerate(partition_ids(ids, output, batches)):
            part = output / f"references-{index}.osm"
            stage = f"referenceBatch{index}"
            commands[stage] = stream_command(["osmium", "getid", "--add-referenced", "--id-file", str(id_file), str(source), "-f", "osm", "-o", "-"], part, output, stage, monitor)
            artifact(part)
            parts.append(part)
        if len(parts) == 1:
            with parts[0].open("rb") as stream: commands["mergeReferences"] = {"copyAdvice": copy_advised(stream, xml)}
        else:
            commands["mergeReferences"] = stream_command(["osmium", "merge", *map(str, parts), "-f", "osm", "-o", "-"], xml, output, "mergeReferences", monitor)
    commands["checkReferences"] = command(["osmium", "check-refs", "--check-relations", str(xml)], output, "checkReferences", monitor)
    return xml, selection, commands


def fixtures(inputs, output, batches):
    rows = []
    for index in range(6):
        original = inputs / "coverage-pilot/staged-calibration-v2-r4/fixtures" / str(index)
        target = output / "fixtures" / str(index)
        target.mkdir(parents=True)
        xml, selection, _ = prepare(original / "region.osm.pbf", [-1, -1, 1, 1], target, batches=batches)
        model = {"id": "exploratory-static-car-v3", "signalDelayMs": 5000, "uTurnDelayMs": 20000}
        graph, audit = import_barriers(xml, target / "barrier.osm", [-1, -1, 1, 1], model)
        old_graph, old_audit = import_barriers(original / "old/car-roads.osm", target / "old-barrier.osm", [-1, -1, 1, 1], model)
        if b"".join(encoded_blocks(graph_data(graph, model))) != b"".join(encoded_blocks(graph_data(old_graph, model))) or audit != old_audit:
            raise ValueError(f"Sparse fixture differs: {index}")
        rows.append({"fixture": index, "graphIdentity": graph.identity, "auditSha256": digest(audit), "graphAndAuditIdentical": True,
                     "originalSourceArtifact": artifact(original / "source.osm"), "selection": selection})
    return rows

