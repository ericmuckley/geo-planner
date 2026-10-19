"""Fresh streamed source-evidence and uncertainty excerpt parity fixtures."""

import copy
from pathlib import Path
import tempfile

from barrier_policy_test import MODEL
from barriers import PORT
from base_id_import import import_barriers
from compact_storage import encoded_blocks
from evidence_fixtures import CASES, sha, source_xml
from targeted_evidence import source_examples as frozen_examples
from crossing_audit import source_uncertainties as frozen_uncertainties
from xml_evidence import source_examples, source_uncertainties


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


def uncertainty_cases():
    source = '<osm><node id="2" lon="0" lat="0"/><node id="1" lon="1" lat="0"/>'
    source += '<way id="10"><nd ref="2"/><nd ref="1"/><tag k="fixme" v="border access unclear"/><tag k="name" v="México &amp; US 🌎"/></way></osm>'
    yield "hint-and-unicode", source
    yield "empty", '<osm/>'
    yield "unmarked", source.replace('border access unclear', 'ordinary note')
    yield "duplicate-and-missing-node", source.replace('</osm>', '<way id="10"><nd ref="99"/><tag k="fixme" v="checkpoint barrier unclear"/></way></osm>')
    yield "malformed", source + '<broken'
    yield "invalid-reference", source.replace('<nd ref="2"', '<nd ref="bad"', 1)


def compare_uncertainty(directory, name, source):
    path = directory / "source.osm"
    path.write_text(source)
    results, errors, outputs = [], [], []
    for index, function in enumerate((frozen_uncertainties, source_uncertainties)):
        output = directory / f"uncertain-{index}.osm"
        try:
            results.append(function(path, output)); errors.append(None)
        except (ValueError, SyntaxError) as error:
            results.append(None); errors.append({"type": type(error).__name__, "message": str(error)})
        outputs.append(output.read_bytes() if output.exists() else None)
    assert results[0] == results[1] and errors[0] == errors[1] and outputs[0] == outputs[1], name
    assert bool(errors[1]) == (name in {"malformed", "invalid-reference"})
    return {"name": name, "sourceSha256": sha(source.encode()), "failure": errors[1],
            "rowsSha256": sha(b"".join(encoded_blocks(results[1]))),
            "excerptSha256": sha(outputs[1]) if outputs[1] is not None else None}


def qualify():
    controls, uncertainties = [], []
    for name in CASES:
        with tempfile.TemporaryDirectory() as temporary: controls.append(compare(Path(temporary), name))
    for name, source in uncertainty_cases():
        with tempfile.TemporaryDirectory() as temporary: uncertainties.append(compare_uncertainty(Path(temporary), name, source))
    return {"controlCases": controls, "uncertaintyCases": uncertainties,
            "caseCount": len(controls) + len(uncertainties),
            "successes": sum(row["failure"] is None for row in controls + uncertainties),
            "failuresMatched": sum(row["failure"] is not None for row in controls + uncertainties),
            "scope": "Fresh synthetic streamed source/uncertainty fixtures. Return/audit/excerpt bytes and exception type/message/priority match frozen readers. No new regional search qualification."}

