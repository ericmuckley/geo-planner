"""Synthetic source-evidence and failure parity against the frozen implementation."""

import copy
import hashlib
from pathlib import Path
import tempfile

from barrier_policy_test import MODEL
from barriers import PORT, SOURCE_NODES, source_examples as frozen_examples
from compact_storage import encoded_blocks
from member_import import import_barriers
from targeted_evidence import source_examples


def source_xml(mixed=False, isolated=False, port_closed=False, extra=False):
    nodes, ways = [], []
    for index, node in enumerate(sorted(SOURCE_NODES)):
        left, right = 10_000 + index * 2, 10_001 + index * 2
        permission = "no" if (port_closed and node == PORT) or (mixed and node != PORT) else "yes"
        nodes.append(f'<node id="{node}" lon="{index / 100}" lat="0"><tag k="barrier" v="border_control"/><tag k="motorcar" v="{permission}"/></node>')
        nodes += [f'<node id="{left}" lon="{index / 100 - .001}" lat="0"/>', f'<node id="{right}" lon="{index / 100 + .001}" lat="0"/>']
        if not (isolated and node != PORT):
            ways.append(f'<way id="{100 + index}"><nd ref="{left}"/><nd ref="{node}"/><nd ref="{right}"/><tag k="highway" v="residential"/><tag k="oneway" v="yes"/></way>')
    for index in range(32): nodes.append(f'<node id="{20_000 + index}" lon="{index / 1000}" lat=".1"/>')
    ways.append('<way id="200">' + ''.join(f'<nd ref="{20_000 + index}"/>' for index in range(32)) + '<tag k="highway" v="residential"/></way>')
    if extra:
        ways.append(f'<way id="300"><nd ref="20000"/><nd ref="{PORT}"/><tag k="highway" v="service"/><tag k="service" v="parking_aisle"/><tag k="name" v="México &amp; US 🌎"/></way>')
    return '<osm version="0.6">' + ''.join(nodes + ways) + '</osm>'


CASES = ("permitted", "mixed-closures", "isolated-controls", "excluded-incident-way", "reordered-decisions",
         "missing-decision", "closed-with-through-transition", "port-closed", "malformed-xml", "invalid-way-reference", "missing-before-malformed")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compare(directory, name):
    source = source_xml(mixed=name == "mixed-closures", isolated=name == "isolated-controls",
                        port_closed=name == "port-closed", extra=name == "excluded-incident-way")
    path = directory / "source.osm"
    path.write_text(source)
    graph, original = import_barriers(path, directory / "prepared.osm", [-1, -1, 1, 1], MODEL)
    decisions = original["barrierPolicy"]["decisions"]
    if name == "reordered-decisions": decisions.reverse()
    if name in {"missing-decision", "missing-before-malformed"}: decisions.pop()
    if name == "closed-with-through-transition":
        next(row for row in decisions if row["id"] != PORT)["blockedByModel"] = True
    if name in {"malformed-xml", "missing-before-malformed"}: source += '<broken'
    if name == "invalid-way-reference": source = source.replace('<nd ref="10000"', '<nd ref="invalid"', 1)
    path.write_text(source)
    audits, results, errors, outputs = [], [], [], []
    measurements, stages = {}, []
    for index, function in enumerate((frozen_examples, source_examples)):
        audit = copy.deepcopy(original)
        output = directory / f"excerpt-{index}.osm"
        try:
            result = function(path, output, graph, audit) if index == 0 else function(path, output, graph, audit, measurements, stages.append)
            errors.append(None); results.append(result)
        except (ValueError, SyntaxError) as error:
            errors.append({"type": type(error).__name__, "message": str(error)}); results.append(None)
        audits.append(audit)
        outputs.append(output.read_bytes() if output.exists() else None)
    assert errors[0] == errors[1] and results[0] == results[1] and audits[0] == audits[1] and outputs[0] == outputs[1], name
    expected_failure = name in CASES[5:]
    assert bool(errors[1]) == expected_failure, name
    if name in {"missing-decision", "missing-before-malformed"}: assert errors[1]["message"] == "A source-backed barrier fixture is missing"
    if name == "closed-with-through-transition": assert errors[1]["message"] == "Closed source-backed barrier has a through transition"
    if name == "port-closed": assert errors[1]["message"] == "Explicit car permission did not admit the real port transition"
    stats = measurements["index"]
    assert stats["incomingNodes"] <= 5 and stats["outgoingNodes"] <= 5
    assert stats["incomingReferences"] + stats["outgoingReferences"] < stats["scannedRoads"]
    return {"name": name, "sourceSha256": sha(source.encode()), "graphIdentity": graph.identity, "failure": errors[1],
            "auditSha256": sha(b"".join(encoded_blocks(audits[1]))), "excerptSha256": sha(outputs[1]) if outputs[1] is not None else None,
            "index": stats, "observedStages": stages}


def qualify():
    results = []
    for name in CASES:
        with tempfile.TemporaryDirectory() as temporary: results.append(compare(Path(temporary), name))
    return {"caseCount": len(results), "successes": sum(row["failure"] is None for row in results),
            "failuresMatched": sum(row["failure"] is not None for row in results), "cases": results,
            "scope": "Fresh synthetic control-point/source fixtures. Return values, mutated audit, excerpt bytes, exception type/message and error priority match the frozen source_examples function. No regional search qualification."}
