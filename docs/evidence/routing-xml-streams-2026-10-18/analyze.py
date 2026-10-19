"""Audit range-aware XML parity, read lifetimes and complete-container use."""

import ast
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = ("downtown-v2", "corridor-v3", "wide-v3", "hour-v3")
CAP = 4 * 1024**3


def read(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def resources(report):
    rows = list(report["resourceCheckpoints"].values())
    assert all(row["memory.max"] == str(CAP) and row["memory.swap.max"] == "0" for row in rows)
    assert all(row["memory.swap.current"] == row["memory.swap.peak"] == "0" for row in rows)
    events = {key: max(int(row["memory.events"][key]) for row in rows) for key in ("max", "oom", "oom_kill", "oom_group_kill")}
    peak = max(int(row["memory.peak"]) for row in rows)
    return {"cgroupPeakBytes": peak, "workerPeakRssKiB": max(row["workerMaxRssKiB"] for row in rows),
            "events": events, "wallMs": report["workerWallMs"], "importMs": report["importMs"],
            "peakWith25PercentMarginBytes": math.ceil(peak * 1.25),
            "phaseHeadroomPass": not any(events.values()) and math.ceil(peak * 1.25) < CAP}


def check_code():
    def function(file, name):
        return next(node for node in ast.parse((ROOT / "routing" / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
    assert ast.dump(function("cache_import.py", "import_barriers")) == ast.dump(function("member_import.py", "import_barriers"))
    old, new = function("input_import.py", "resolve"), function("member_lookup.py", "resolve")
    old.args = new.args
    guards = [node for node in ast.walk(old) if isinstance(node, ast.If) and any(isinstance(child, ast.Constant) and child.value == "Duplicate directed road geometry" for child in ast.walk(node))]
    assert len(guards) == 1
    guards[0].test = ast.Name(id="duplicate_geometry", ctx=ast.Load())
    assert ast.dump(old) == ast.dump(new)
    for name, expected in read("new-recipe-sha256.json").items():
        assert sha(ROOT / "routing" / name) == expected
    for name, expected in read("preserved-sha256.json").items():
        assert sha(ROOT / name) == expected, name


def check_source_body():
    def function(file):
        return next(node for node in ast.parse((ROOT / "routing" / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == "source_examples")
    original, current = function("barriers.py"), function("targeted_evidence.py")
    current.args = original.args
    scan = next(index for index, node in enumerate(current.body) if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "selected_incidence")
    current.body[1:scan + 2] = original.body[1:3]
    class RemoveMarks(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "mark": return None
            return node
    current = RemoveMarks().visit(current)
    assert ast.dump(original) == ast.dump(current)


def check_base_body():
    def function(file, name):
        return next(node for node in ast.parse((ROOT / "routing" / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
    original = function("compact_storage.py", "build_graph")
    string = function("base_ids.py", "string_build_graph")
    class RemoveProfile(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "mark": return None
            return node
        def visit_Assign(self, node):
            if any(isinstance(target, ast.Name) and target.id == "mark" for target in node.targets): return None
            return node
        def visit_If(self, node):
            if isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "measurements": return None
            return self.generic_visit(node)
    string = RemoveProfile().visit(string)
    string.name, string.args = original.name, original.args
    assert ast.dump(original) == ast.dump(string)
    ordered = function("base_ids.py", "ordered_build_graph")
    def routing_body(node):
        start = next(index for index, item in enumerate(node.body) if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "rules" for target in item.targets))
        end = next(index for index, item in enumerate(node.body) if isinstance(item, ast.Delete))
        return [ast.dump(item) for item in node.body[start:end] if not (isinstance(item, ast.Expr) and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "mark")]
    assert routing_body(ordered) == routing_body(original)
    original, current = function("input_import.py", "build_base"), function("base_id_input.py", "build_base")
    current.args = original.args
    call = next(node for node in ast.walk(current) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_graph")
    call.args = call.args[:5]
    assert ast.dump(original) == ast.dump(current)


def check_xml_body():
    def function(file, name):
        return next(node for node in ast.parse((ROOT / "routing" / file).read_text()).body if isinstance(node, ast.FunctionDef) and node.name == name)
    class UnwrapReadContext(ast.NodeTransformer):
        def visit_With(self, node):
            node = self.generic_visit(node)
            context = node.items[0]
            if isinstance(context.context_expr, ast.Call) and isinstance(context.context_expr.func, ast.Name) and context.context_expr.func.id == "parse_xml":
                call = context.context_expr
                call.func = ast.Attribute(value=ast.Name(id="ET", ctx=ast.Load()), attr="iterparse", ctx=ast.Load())
                return [ast.Assign(targets=[context.optional_vars], value=call)] + node.body
            return node
    for old, name in (("targeted_evidence.py", "source_examples"), ("crossing_audit.py", "source_uncertainties")):
        assert ast.dump(function(old, name)) == ast.dump(UnwrapReadContext().visit(function("xml_evidence.py", name)))


def analyze():
    check_code()
    check_source_body()
    check_base_body()
    check_xml_body()
    results = {}
    for case in CASES:
        report, manifest = read(f"streamed-{case}-report.json"), read(f"streamed-{case}-manifest.json")
        identity = read(f"streamed-{case}-run-identity.json")
        old, original = read(f"ids-{case}-manifest.json"), read(f"qualified-{case}-manifest.json")
        baseline = read(f"ids-{case}-report.json")
        assert report["runId"] == manifest["runId"] == identity["runId"]
        unsigned = {key: value for key, value in identity.items() if key != "runId"}
        assert identity["runId"] == hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        assert manifest["imageId"] == old["imageId"] and manifest["network"] == "none" and manifest["cpus"] == 2
        assert manifest["memoryLimit"] == manifest["memorySwapLimit"] == "4g" and manifest["swapPolicy"] == "disabled"
        assert report["publicApiCalls"] == 0 and not report["coverageVerified"]
        assert report["graphIdentity"] == old["graphIdentity"] == original["graphIdentity"]
        assert manifest["sourceArtifact"] == old["sourceArtifact"] == original["sourceArtifact"]
        assert manifest["profile"] == old["profile"] == original["profile"]
        assert manifest["previousManifestSha256"] == sha(HERE / f"ids-{case}-manifest.json")
        assert manifest["previousReportSha256"] == sha(HERE / f"ids-{case}-report.json")
        assert manifest["qualificationManifestSha256"] == sha(HERE / f"qualified-{case}-manifest.json")
        assert manifest["artifacts"]["report.json"] == artifact(HERE / f"streamed-{case}-report.json")
        for script, expected in manifest["scripts"].items(): assert sha(ROOT / "routing" / script) == expected, script
        assert len(report["artifacts"]) == {"downtown-v2": 4, "corridor-v3": 6, "wide-v3": 7, "hour-v3": 7}[case]
        assert all(value == old["artifacts"][name] == original["artifacts"][name] for name, value in report["artifacts"].items())
        assert all(report["identicalArtifactSha256"][name] == value["sha256"] for name, value in report["artifacts"].items())
        reused = report["reusedQualification"]
        assert reused == baseline["reusedQualification"]
        assert reused["manifestSha256"] == manifest["qualificationManifestSha256"]
        assert reused["artifacts"] == {name: value for name, value in original["artifacts"].items() if name == "summary.json" or name.startswith("oracles/")}
        fixture = read(f"streamed-{case}-fixture-parity.json")
        assert report["fixtureParity"] == manifest["artifacts"]["fixture-parity.json"] == artifact(HERE / f"streamed-{case}-fixture-parity.json")
        assert fixture["caseCount"] == len(fixture["cases"]) == 17
        assert fixture["fullCostComparisons"] == sum(row["states"] ** 2 for row in fixture["cases"])
        assert fixture["boundedCostComparisons"] == 3 * fixture["fullCostComparisons"]
        reasons = {row["name"]: row["fallbackReasons"] for row in fixture["cases"]}
        assert reasons["unselected-duplicate"] == [{"id": 99, "reason": "Duplicate directed road geometry"}]
        assert reasons["ambiguous-before-duplicate"] == [{"id": 99, "reason": "ambiguous/disconnected member join"}]
        assert reasons["selected-duplicate"] == [{"id": 99, "reason": "missing, closed or repeated-node member way"}]
        assert report["idMode"] == manifest["idMode"] == identity["idMode"] == "ordered"
        profiles = report["importStages"]["baseGraphProfiles"]
        assert len(profiles) == report["importStages"]["baseBuilds"]
        for row in profiles:
            assert row["mode"] == row["requestedMode"] == "ordered"
            assert row["orderedKeyFastPath"] and not row["fallbackToStrings"]
            assert row["idKeysRetained"] == 1 and row["idSetShallowBytes"] == row["idStringShallowBytes"] == 0
            assert row["outgoingContainerBytes"] > 0 and row["outgoingReferences"] >= row["outgoingNodes"] > 0
            assert set(row["phaseMs"]) == {"outgoingReady", "rulesReady", "arcsBuilt", "indexesReleased", "baseHashed"}
        source_fixture = read(f"streamed-{case}-evidence-fixtures.json")
        assert report["evidenceFixtures"] == manifest["artifacts"]["evidence-fixtures.json"] == artifact(HERE / f"streamed-{case}-evidence-fixtures.json")
        assert source_fixture["caseCount"] == len(source_fixture["cases"]) == 11
        assert source_fixture["successes"] == 5 and source_fixture["failuresMatched"] == 6
        for row in source_fixture["cases"]:
            assert row["index"]["incomingNodes"] <= 5 and row["index"]["outgoingNodes"] <= 5
        stage = report["sourceEvidenceStages"]
        if case.endswith("v3"):
            assert stage["index"]["scannedRoads"] == report["roads"]
            assert stage["index"]["selectedNodes"] == 5
            assert stage["index"]["incomingNodes"] <= 5 and stage["index"]["outgoingNodes"] <= 5
            assert set(stage["phaseMs"]) == {"sourceIndexes", "sourceTransitions", "sourceWayScan", "sourceNodeScan", "sourceExcerpt"}
            assert all(value >= 0 for value in stage["phaseMs"].values())
        else: assert stage == {}
        xml_fixture = read(f"streamed-{case}-xml-fixtures.json")
        assert report["xmlFixtures"] == manifest["artifacts"]["xml-fixtures.json"] == artifact(HERE / f"streamed-{case}-xml-fixtures.json")
        assert xml_fixture["caseCount"] == 17 and xml_fixture["successes"] == 9 and xml_fixture["failuresMatched"] == 8
        assert len(xml_fixture["controlCases"]) == 11 and len(xml_fixture["uncertaintyCases"]) == 6
        policy = report["xmlStreams"]
        assert policy["windowBytes"] == 16 * 1024**2 and policy["readThresholdBytes"] == 8 * 1024**2
        assert all(row["closed"] for row in policy["requests"])
        real_reads = [row for row in policy["requests"] if row["path"].startswith("/inputs/")]
        assert len(real_reads) == {"downtown-v2": 0, "corridor-v3": 2, "wide-v3": 4, "hour-v3": 4}[case]
        for row in real_reads:
            assert row["fileBytes"] == row["readBytes"] == row["successfulAdviceBytes"] == row["attemptedBytes"] == manifest["sourceArtifact"]["bytes"]
            assert row["enabled"] and row["eofObserved"] and row["adviceErrors"] == 0 and row["lastAdviceError"] is None
            assert row["windowBytes"] == policy["windowBytes"] and row["ranges"] == math.ceil(row["fileBytes"] / row["windowBytes"])
            assert 0 < row["maxRangeBytes"] <= row["windowBytes"] and 0 < row["maxReadBytes"] <= 65536
        lookup = report["importStages"]["memberRoadLookups"]
        assert len(lookup) == report["importStages"]["sharedRoadLookupBuilds"]
        assert all(row["retainedKeys"] <= row["memberRoadsScanned"] <= row["totalRoads"] for row in lookup)
        assert all(row["duplicateRoads"] == 0 and row["scanMs"] > 0 for row in lookup)
        assert all(row["retainedKeys"] < row["totalRoads"] for row in lookup)
        assert report["ioLifetime"]["windowBytes"] == 16 * 1024**2
        for row in report["cacheAdvice"]["requests"]:
            assert row["windowBytes"] == 16 * 1024**2 and row["ranges"] == math.ceil(row["bytes"] / row["windowBytes"])
        measured = resources(report)
        assert measured["phaseHeadroomPass"] and not any(measured["events"].values())
        results[case] = {"before": resources(baseline), "after": measured,
                         "graphIdentity": report["graphIdentity"], "states": report["states"], "arcs": report["transitions"],
                         "identicalArtifacts": len(report["artifacts"]), "fixtureCases": fixture["caseCount"],
                         "maxRetainedKeys": max(row["retainedKeys"] for row in lookup),
                         "maxScannedRoads": max(row["totalRoads"] for row in lookup),
                         "maxWayKeys": max(row["maxWayKeys"] for row in lookup),
                         "lookupScanMs": sum(row["scanMs"] for row in lookup),
                         "sourceEvidenceStages": stage, "sourceFixtureCases": source_fixture["caseCount"],
                         "maxOutgoingContainerBytes": max(row["outgoingContainerBytes"] for row in profiles),
                         "maxOutgoingNodes": max(row["outgoingNodes"] for row in profiles),
                         "idDispatchMs": sum(row["idDispatchMs"] for row in profiles),
                         "sourceXmlPasses": len(real_reads), "sourceXmlBytes": sum(row["readBytes"] for row in real_reads),
                         "sourceXmlAdviceRanges": sum(row["ranges"] for row in real_reads), "newXmlFixtureCases": xml_fixture["caseCount"]}
    current = read("streamed-hour-v3-report.json")
    native, qualified = read("frozen-native-verification.json"), read("frozen-qualification-report.json")
    assert native["graphIdentity"] == qualified["graphIdentity"] == current["graphIdentity"]
    assert native["sourceManifestSha256"] == sha(HERE / "qualified-hour-v3-manifest.json")
    assert native["compilation"]["sourceSha256"] == sha(ROOT / "routing/native_search.cpp")
    assert native["costComparisons"] == current["states"] * 45 and native["membershipComparisons"] == current["states"] * 40
    assert qualified["costComparisons"] == current["states"] * 5 and qualified["boundedCostComparisons"] == current["states"] * 40
    assert native["interiorDestinationComparisons"] == qualified["interiorDestinationComparisons"] == 2
    assert current["reusedQualification"]["nativeVerification"] == artifact(HERE / "frozen-native-verification.json")
    assert current["reusedQualification"]["qualificationReport"] == artifact(HERE / "frozen-qualification-report.json")
    for case in CASES[:-1]:
        assert read("streamed-hour-v3-manifest.json")["parityReports"][case] == sha(HERE / f"streamed-{case}-report.json")
    return {"cases": results, "newLargerGraphBuilt": False, "coverageVerified": False,
            "scope": "Exact frozen graph/source/audit/CSR/gzip parity; fresh source-evidence/failure and importer fixture checks and reused regional independent/native evidence. Complete capped observations include verification reads; no fresh regional searches, HTTP, contour, browser or Vercel timing. Cache/host/VM conditions uncontrolled; current phase headroom is not larger-graph admission."}


if __name__ == "__main__": print(json.dumps(analyze(), indent=2, sort_keys=True))
