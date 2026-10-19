"""Verify paged-ID calibration, all-frontier planning and two-hour resource admission."""

import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "routing"))
from anchors import digest
from two_hour_admission import evaluate
from two_hour_frontier import plan
from hour_admission import peak


def read(path): return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream: return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    assert path.stat().st_size == expected["bytes"], path
    assert sha(path) == expected["sha256"], path


def run():
    reports = {}
    for key in ("calibration", "candidate"):
        directory = ROOT / "data/coverage-pilot" / f"two-hour-{key}-v1"
        identity, report = read(directory / "identity.json"), read(directory / "report.json")
        assert identity["runId"] == digest({k:v for k,v in identity.items() if k != "runId"}) == report["runId"]
        assert identity == read(HERE / f"{key}-identity.json") and report == read(HERE / f"{key}-report.json")
        for name, expected in identity["scripts"].items():
            assert sha(ROOT / "routing" / name) == sha(directory / "recipe" / name) == expected
        for name, expected in report["artifacts"].items(): check(directory / name, expected)
        assert identity["memoryLimit"] == identity["memorySwapLimit"] == "4g"
        assert identity["cpus"] == 2 and identity["network"] == "none"
        assert not report["publicApiCalls"] and not report["fullGraphBuilt"] and not report["coverageVerified"]
        peak(report)
        storage = report["selection"]["nodeStorage"]
        assert storage["ids"] == report["selection"]["insideNodes"]
        assert storage["bitmapBytes"] == storage["allocatedPages"] * 512 and storage["idsPerPage"] == 4096
        assert report["profileSha256"] == sha(ROOT / "routing/profiles/coverage-two-hour-v1.json") == sha(directory / "recipe/coverage-two-hour-v1.json")
        assert report["wheelLockSha256"] == sha(ROOT / "routing/tools/pyosmium-v1.json") == sha(directory / "recipe/pyosmium-v1.json")
        reports[key] = report
    calibration, candidate = reports["calibration"], reports["candidate"]
    assert len(calibration["fixtures"]) == 6 and all(x["graphAndAuditIdentical"] for x in calibration["fixtures"])
    assert calibration["xmlByteIdentical"] and not candidate["xmlByteIdentical"]
    assert calibration["scripts"] == candidate["scripts"] and calibration["profile"] == candidate["profile"]
    assert calibration["imageId"] == candidate["imageId"] == read(ROOT / "data/tools/sparse-image-v1.json")["imageId"]
    assert candidate["calibrationReportSha256"] == sha(ROOT / "data/coverage-pilot/two-hour-calibration-v1/report.json")
    source = ROOT / "data/compact-pilot/hour-v3"
    manifest = read(source / "manifest.json")
    for name, expected in manifest["artifacts"].items(): check(source / name, expected)
    assert candidate["sourceManifestSha256"] == calibration["sourceManifestSha256"] == sha(source / "manifest.json")
    assert calibration["artifacts"]["car-roads.osm"] == manifest["sourceArtifact"]
    assert calibration["candidate"] == read(ROOT / "data/coverage-pilot/hour-candidate-v1/report.json")["candidate"]
    native, qualified = read(source / "native-verification.json"), read(source / "qualification-report.json")
    assert native == read(ROOT / "docs/evidence/hour-qualification-2026-10-17/native-verification.json")
    assert qualified == read(ROOT / "docs/evidence/hour-qualification-2026-10-17/qualification-report.json")
    assert native["sourceManifestSha256"] == sha(source / "manifest.json")
    assert native["compilation"]["sourceSha256"] == sha(ROOT / "routing/native_search.cpp")
    assert native["compilation"]["binarySha256"] == sha(source / "native_search")
    assert candidate["nativeReportSha256"] == sha(source / "native-verification.json")
    assert candidate["qualificationReportSha256"] == sha(source / "qualification-report.json")
    cut_directory = ROOT / "data/compact-pilot/hour-v3-cuts"
    cuts = read(cut_directory / "report.json")
    assert cuts["sourceManifestSha256"] == sha(source / "manifest.json") and cuts["nodesWithoutBoundaryLinks"] == 0
    for name, expected in cuts["artifacts"].items(): check(cut_directory / name, expected)
    check(ROOT / "data/valhalla-v2/region.osm.pbf", candidate["regionArtifact"])
    parent = read(ROOT / "data/valhalla-v2/build-complete.json")["manifest"]["bbox"]
    frontier = plan(read(cut_directory / "cut-nodes.json"), manifest["profile"]["bbox"], parent)
    assert frontier == calibration["frontier"] == candidate["frontier"]
    assert frontier["originCutPairs"] == 550 and frontier["reachedCutNodes"] == 116
    assert frontier["candidateBounds"] == candidate["profile"]["bbox"]
    assert candidate["cutReportSha256"] == sha(cut_directory / "report.json")
    built = read(source / "build-report.json")
    rebuilt_path = ROOT / "data/compact-pilot/hour-v3-rebuild/build-report.json"
    assert candidate["buildReportSha256"] == sha(source / "build-report.json") and candidate["rebuildReportSha256"] == sha(rebuilt_path)
    admission = evaluate(calibration, candidate, candidate["candidate"], built, read(rebuilt_path), qualified, native, cuts, frontier)
    assert admission == candidate["admission"]
    def body(path, name):
        return ast.dump(next(x for x in ast.parse(path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name == name))
    for name in ("prepare", "fixtures"):
        assert body(ROOT / "routing/sparse_prepare.py", name) == body(ROOT / "routing/two_hour_prepare.py", name)
    original_tree = ast.parse((ROOT / "routing/sparse_select.py").read_text())
    paged_tree = ast.parse((ROOT / "routing/paged_select.py").read_text())
    original = next(x for x in original_tree.body if isinstance(x,ast.FunctionDef) and x.name == "select_ids")
    paged = next(x for x in paged_tree.body if isinstance(x,ast.FunctionDef) and x.name == "select_ids")
    scope = next(n.value for n in ast.walk(original) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith("Sparse sets contain"))
    class StorageOnly(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id == "PagedIdSet": node.func.id = "set"
            return node
        def visit_Dict(self, node):
            self.generic_visit(node)
            pairs=[(k,v) for k,v in zip(node.keys,node.values) if not isinstance(k,ast.Constant) or k.value != "nodeStorage"]
            node.keys=[k for k,v in pairs];node.values=[ast.Constant(scope) if isinstance(k,ast.Constant) and k.value == "scope" else v for k,v in pairs]
            return node
    assert ast.dump(original) == ast.dump(StorageOnly().visit(paged))
    previous = read(ROOT / "data/coverage-pilot/hour-candidate-v1/report.json")
    def resource(report):
        last = max(report["resourceCheckpoints"].values(), key=lambda x:x["elapsedMs"])
        return {"workerWallMs":report["workerWallMs"], "cgroupPeakBytes":peak(report)[0], "limitPressure":peak(report)[1],
                "workerMaxRssKiB":last["workerMaxRssKiB"], "maxChildRssKiB":last["maxChildRssKiB"], "sampling":report["sampling"]}
    comparison = {"frontier":frontier, "admission":admission, "calibrationXmlAndCensusIdentical":True, "sixFixtureGraphsAndAuditsIdentical":True,
                  "candidateCounts":candidate["candidate"], "candidateSourceArtifact":candidate["artifacts"]["car-roads.osm"],
                  "nodeStorage":{k:r["selection"]["nodeStorage"] for k,r in reports.items()},
                  "resources":{k:resource(r) for k,r in {**reports,"previousSameSourcePreparation":previous}.items()},
                  "nativeEvidenceReusedByExactIdentity":True,"newNativeRuns":0,"newGraphs":0,"publicRoutingApiCalls":0,"newDownloads":0,"coverageVerified":False}
    admission.update({"candidateSourceArtifact":candidate["artifacts"]["car-roads.osm"], "sourceReportSha256":{k:sha(ROOT / "data/coverage-pilot" / f"two-hour-{k}-v1/report.json") for k in reports},
                      "admissionRuleSha256":sha(ROOT / "routing/two_hour_admission.py")})
    (HERE / "admission.json").write_text(json.dumps(admission,indent=2)+'\n')
    (HERE / "comparison.json").write_text(json.dumps(comparison,indent=2)+'\n')
    print(json.dumps({"frontier":frontier,"admission":admission},indent=2))


if __name__ == "__main__": run()
