"""Require qualified graph proofs and the selected two-hour boundary milestone."""

import argparse
import json
from pathlib import Path

from anchors import file_hash, load_json
from region_release import ROOT, check_resources, compare_barriers, require, run as check_graph
from increment import check_scripts
from scoped_region_verification_v3 import check_sinks


def two_hour_check(origins):
    require(len(origins) == 5, "Expected all five reference origins")
    result = []
    for origin in origins:
        budgets = [row for row in origin["budgets"] if row["budgetMs"] == 7200000]
        require(len(budgets) == 1, "Missing two-hour boundary observation")
        require(budgets[0]["reachableCutNodes"] == 0, "A reference origin still reaches a data edge within two hours")
        require(origin["firstCutExitMs"] is None or origin["firstCutExitMs"] > 7200000, "First-edge cost contradicts the boundary count")
        result.append({"origin": origin["origin"], "firstCutExitMs": origin["firstCutExitMs"], "reachedAt120Minutes": 0})
    require(len({row["origin"] for row in result}) == 5, "Reference origin repeated")
    return result


def run(name):
    directory = ROOT / "data/compact-pilot" / name
    target = directory / "two-hour-acceptance.json"
    require(not target.exists(), "Preserve acceptance evidence")
    check_graph(name, name + "-rebuild", name + "-cuts")
    released = load_json(directory / "release.json")
    cuts = load_json(ROOT / "data/compact-pilot" / (name + "-cuts") / "report.json")
    previous = ROOT / "data/compact-pilot/experiment-region-v1"
    old_summary, summary = load_json(previous / "summary.json"), load_json(directory / "summary.json")
    policy = load_json(ROOT / "data/compact-pilot/scoped-current-v1/calibration-report.json")
    require(policy["routingPayloadUnchanged"], "Scoped-policy calibration failed")
    manifest = load_json(directory / "manifest.json")
    require(manifest["policyCalibrationReportSha256"] == file_hash(ROOT / "data/compact-pilot/scoped-current-v1/calibration-report.json"), "Scoped-policy evidence changed after qualification")
    check_sinks(directory, ROOT / "data")
    require(manifest["reusedSinkCalibrationIdentitySha256"] == file_hash(directory / "qualification-identity.json"), "Reference-sink identity changed after qualification")
    check_scripts(ROOT / "data/compact-pilot" / (name + "-cuts"), cuts["scripts"])
    native = load_json(directory / "native-verification.json")
    require(native["workerSha256"] == file_hash(ROOT / "routing/scoped_native.py"), "Native verifier changed")
    require(native["loaderSha256"] == file_hash(ROOT / "routing/scoped_load.py"), "Native loader differs")
    require({row["restriction"]["id"] for row in old_summary["sourceSamples"]} <= {row["restriction"]["id"] for row in summary["sourceSamples"]}, "A qualified maneuver fixture disappeared")
    require({row["origin"] for row in cuts["origins"]} == {row["origin"] for row in old_summary["origins"]}, "Reference origins changed")
    observations = two_hour_check(cuts["origins"])
    routes = {(row["origin"], row["destination"]): row for row in summary["sampledRoutes"]}
    route_comparisons = []
    for old in old_summary["sampledRoutes"]:
        new = routes[old["origin"], old["destination"]]
        require(new["costMs"] is not None and new["costMs"] <= old["costMs"], "A prior city route regressed")
        route_comparisons.append({"origin": old["origin"], "destination": old["destination"],
                                  "previousCostMs": old["costMs"], "costMs": new["costMs"], "roadIdsIdentical": old["roadIds"] == new["roadIds"]})
    old_audit, audit = load_json(previous / "import-audit.json"), load_json(directory / "import-audit.json")
    require({row["id"] for row in old_audit["viaWayRestrictions"]} <= {row["id"] for row in audit["viaWayRestrictions"]}, "A previously qualified via-way prohibition disappeared")
    changes = compare_barriers(old_audit["barrierPolicy"]["decisions"], audit["barrierPolicy"]["decisions"],
                               old_summary["profile"]["bbox"], summary["profile"]["bbox"])
    prepared_dir = ROOT / "data/coverage-pilot/two-hour-region-v2"
    prepared = load_json(prepared_dir / "report.json")
    source_dir = ROOT / "data/source-pilot" / prepared["sourceRun"]
    source = load_json(source_dir / "report.json")
    require(file_hash(source_dir / "report.json") == prepared["sourceReportSha256"], "Source provenance changed")
    report = {"graphIdentity": released["graphIdentity"], "selectedTwoHourBoundaryCheckPassed": True,
              "releaseSha256": file_hash(directory / "release.json"), "previousSummarySha256": file_hash(previous / "summary.json"),
              "preparationReportSha256": file_hash(prepared_dir / "report.json"), "sourceReportSha256": prepared["sourceReportSha256"],
              "policyCalibrationReportSha256": file_hash(ROOT / "data/compact-pilot/scoped-current-v1/calibration-report.json"),
              "additionalResources": {"sourceMerge": check_resources(source), "sourcePreparation": check_resources(prepared)},
              "origins": observations, "cityRouteComparisons": route_comparisons, "newlyCoveredControlPoints": changes,
              "preservedBarrierDecisions": len(old_audit["barrierPolicy"]["decisions"]) - len(changes),
              "workerSha256": file_hash(Path(__file__)), "publicApiCalls": 0, "coverageVerified": False,
              "scope": "No reached potential rectangular cuts at 120 minutes for these five qualified static-model sources. Does not prove source completeness, every origin, real eligibility, traffic ETAs, national or cloud coverage. App/browser verification is separate."}
    with target.open("x") as stream: json.dump(report, stream, indent=2); stream.write("\n")
    print(json.dumps({key: report[key] for key in ("graphIdentity", "selectedTwoHourBoundaryCheckPassed", "origins")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-run", default="two-hour-region-v2")
    args = parser.parse_args()
    if not args.graph_run or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in args.graph_run): parser.error("Invalid run name")
    run(args.graph_run)
