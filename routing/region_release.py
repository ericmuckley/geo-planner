"""Check the expanded graph's build, independent/native proofs and cut inventory."""

import argparse
import json
from pathlib import Path

from anchors import file_hash, load_json
from barrier_policy import barrier_decision
from experiment import artifact, checked_graph
from import_roads import inside


ROOT = Path(__file__).resolve().parent.parent
CAP = 4 * 1024 ** 3


def require(condition, message):
    if not condition: raise ValueError(message)


def check_resources(report):
    checkpoints = report["resourceCheckpoints"].values()
    peak = max(int(row["memory.peak"]) for row in checkpoints)
    for row in checkpoints:
        require(row["memory.max"] == str(CAP), "Container cap changed")
        require(row["memory.swap.max"] == row["memory.swap.current"] == row["memory.swap.peak"] == "0", "Swap observed")
        require(not any(int(row["memory.events"][key]) for key in ("max", "oom", "oom_kill", "oom_group_kill")), "Memory pressure observed")
    require(peak * 1.25 < CAP, "Measured phase lacks 25 percent headroom")
    return {"peakBytes": peak, "with25PercentMarginBytes": round(peak * 1.25), "pressureEvents": 0, "swapBytes": 0}


def compare_barriers(previous, current, previous_bounds, current_bounds):
    decisions = {row["id"]: row for row in current}
    changes = []
    for old in previous:
        new = decisions[old["id"]]
        require(new["point"] == old["point"] and new["tags"] == old["tags"], "Existing control-point source changed")
        if all(new[key] == old[key] for key in ("open", "blockedByModel")): continue
        require(not inside(old["point"], previous_bounds) and inside(new["point"], current_bounds) and old["reason"] == "outside-bounds", "Existing in-region barrier decision changed")
        decision = barrier_decision(new["tags"])
        require(all(new[key] == value for key, value in decision.items()) and new["open"] and not new["blockedByModel"], "Newly covered control violates the unchanged source policy")
        changes.append({"node": old["id"], "point": old["point"], "tags": old["tags"], "previousReason": old["reason"], "reason": new["reason"],
                        "scope": "Previously outside the old rectangle; now inside the new rectangle under the same explicit-permission rule. Real operating/access eligibility remains unverified."})
    return changes


def run(name, rebuild_name, cuts_name):
    directory = ROOT / "data/compact-pilot" / name
    rebuild = ROOT / "data/compact-pilot" / rebuild_name
    cut_directory = ROOT / "data/compact-pilot" / cuts_name
    manifest = checked_graph(directory)
    rebuilt = load_json(rebuild / "build-manifest.json")
    require(rebuilt["graphIdentity"] == manifest["graphIdentity"], "Rebuild graph differs")
    for filename, expected in load_json(directory / "build-manifest.json")["artifacts"].items():
        if filename == "build-report.json": continue
        require(rebuilt["artifacts"][filename] == expected == artifact(rebuild / filename), f"Rebuild bytes differ: {filename}")
    for filename, expected in rebuilt["scripts"].items():
        require(file_hash(rebuild / "recipe" / filename) == expected == file_hash(ROOT / "routing" / filename), "Rebuild recipe changed")
    native = load_json(directory / "native-verification.json")
    cuts = load_json(cut_directory / "report.json")
    manifest_sha = file_hash(directory / "manifest.json")
    for proof in (native, cuts):
        require(proof["sourceManifestSha256"] == manifest_sha and proof["graphIdentity"] == manifest["graphIdentity"], "Proof belongs to a different graph")
    require(native["compilation"]["binarySha256"] == file_hash(directory / "native_search") and native["compilation"]["sourceSha256"] == file_hash(ROOT / "routing/native_search.cpp"), "Native executable/source changed")
    for filename, expected in cuts["artifacts"].items(): require(artifact(cut_directory / filename) == expected, "Cut artifact changed")
    require(cuts["nodesWithoutBoundaryLinks"] == 0, "Boundary source links missing")
    summary = load_json(directory / "summary.json")
    count = summary["states"]
    require(summary["costComparisons"] == count * 5 and summary["boundedCostComparisons"] == count * 40 and summary["interiorDestinationComparisons"] == 2, "Independent checks incomplete")
    require(native["costComparisons"] == count * 45 and native["membershipComparisons"] == count * 40 and native["interiorDestinationComparisons"] == 2, "Native checks incomplete")
    previous = load_json(ROOT / "data/compact-pilot/hour-v3/summary.json")
    routes = {(row["origin"], row["destination"]): row for row in summary["sampledRoutes"]}
    require(len(routes) == 12, "City directions missing")
    comparisons = []
    for old in previous["sampledRoutes"]:
        new = routes[old["origin"], old["destination"]]
        require(new["costMs"] is not None and new["costMs"] <= old["costMs"], "Existing city route regressed")
        comparisons.append({"origin": old["origin"], "destination": old["destination"], "previousCostMs": old["costMs"], "costMs": new["costMs"], "roadIdsIdentical": old["roadIds"] == new["roadIds"]})
    old_audit = load_json(ROOT / "data/compact-pilot/hour-v3/import-audit.json")
    audit = load_json(directory / "import-audit.json")
    changes = compare_barriers(old_audit["barrierPolicy"]["decisions"], audit["barrierPolicy"]["decisions"], previous["profile"]["bbox"], manifest["profile"]["bbox"])
    reports = {"build": load_json(directory / "build-report.json"), "rebuild": load_json(rebuild / "build-report.json"), "qualification": load_json(directory / "qualification-report.json"), "cuts": cuts}
    resources = {stage: check_resources(report) for stage, report in reports.items()}
    require(all(report["publicApiCalls"] == 0 for report in reports.values()), "Unexpected provider requests")
    report = {"qualifiedForLocalExperiment": True, "graphIdentity": manifest["graphIdentity"], "sourceManifestSha256": manifest_sha,
              "nativeReportSha256": file_hash(directory / "native-verification.json"), "cutReportSha256": file_hash(cut_directory / "report.json"),
              "rebuildManifestSha256": file_hash(rebuild / "build-manifest.json"), "workerSha256": file_hash(Path(__file__)),
              "resources": resources, "cityRouteComparisons": comparisons, "preservedBarrierDecisions": len(old_audit["barrierPolicy"]["decisions"]) - len(changes), "newlyCoveredControlPoints": changes,
              "origins": cuts["origins"], "publicApiCalls": 0, "coverageVerified": False,
              "scope": "Qualified regional static graph. Native verification runs separately on macOS; container limits apply to the four measured Linux phases. No source-completeness, real crossing-eligibility, nationwide or cloud-routing claim. Browser/API verification is a separate final step."}
    target = directory / "release.json"
    with target.open("x") as stream: json.dump(report, stream, indent=2); stream.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-run", default="experiment-region-v1")
    parser.add_argument("--rebuild-run")
    parser.add_argument("--cuts-run")
    args = parser.parse_args()
    for name in (args.graph_run, args.rebuild_run, args.cuts_run):
        if name is not None and (not name or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in name)): parser.error("Invalid run name")
    run(args.graph_run, args.rebuild_run or f"{args.graph_run}-rebuild", args.cuts_run or f"{args.graph_run}-cuts")
