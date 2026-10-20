"""Unclipped six-hour planning and admission screening; never builds a graph."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from two_hour_frontier import plan


CURRENT = "compact-pilot/two-hour-region-v2"
CUTS = CURRENT + "-cuts"
PREPARATION = "coverage-pilot/two-hour-region-v2"
BUDGET_MS = 21600000
ORIGINS = {"san-diego", "el-cajon", "tijuana", "san-ysidro", "port-incoming"}
CAP = 4 * 1024**3
COUNT_KEYS = ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments",
              "historyPrefixCeiling", "candidateViaWayRules")


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def frontier(records, current_bounds):
    if not records or any(set(row["origins"]) != ORIGINS for row in records):
        raise ValueError("Require the complete five-source cut inventory")
    # World bounds disable the old helper's parent clipping; they are not a source claim.
    raw = plan(records, current_bounds, [-180, -90, 180, 90], budget_ms=BUDGET_MS)
    if raw["clippedSides"] or raw["candidateBounds"] != raw["roundedBounds"]:
        raise ValueError("Six-hour planning must retain the full outward-rounded envelope")
    reached = {origin: sum(row["origins"][origin]["costMs"] is not None and
                          row["origins"][origin]["costMs"] <= BUDGET_MS for row in records)
               for origin in sorted(ORIGINS)}
    return {key: value for key, value in raw.items() if key not in {"parentBounds", "envelopeContainedInParent", "scope"}} | {
        "cutNodesAccounted": len(records), "cutHistoryStatesAccounted": sum(row["stateCount"] for row in records),
        "reachedByOrigin": reached,
        "scope": "Full 160 km/h spherical continuation envelope, outward rounded to 0.1 degrees, with no cached-parent clipping. All five sources and every recorded cut/history state are retained through the input binding. Conditional on unchanged interior prefixes and the static model speed ceiling; restored topology/restrictions can change prefixes. The enclosing rectangle includes ocean and unreachable corners; it is not minimal acquisition geography or a coverage certificate."}


def admission(candidate, reference, built, observed, source_complete):
    ratios = {key: candidate[key] / reference[key] for key in COUNT_KEYS}
    ratios.update(roadCeiling=candidate["roadStatesUpperBound"] / built["roads"],
                  historyCeiling=candidate["historyStatesUpperBound"] / built["states"])
    scale = max(1, *ratios.values())
    phases = {name: math.ceil(value[0] * (1 if name == "preparation" else scale))
              for name, value in observed.items()}
    estimate = math.ceil(max(phases.values()) * 1.25)
    pressure = any(value[1] for value in observed.values())
    fits = not pressure and estimate < CAP
    return {"decision": "eligible-for-separate-capped-attempt" if fits and source_complete else "hold",
            "eligibleForSeparateBuild": fits and source_complete, "resourceScreenPasses": fits,
            "sourceComplete": source_complete, "ratios": ratios, "scalingRatio": scale,
            "observedReferencePeaksBytes": {name: value[0] for name, value in observed.items()},
            "estimatedPhasePeaksBytes": phases, "wholeWorkflowWith25PercentMarginBytes": estimate,
            "capBytes": CAP, "limitPressure": pressure,
            "scope": "Maximum measured source/restriction/road/history growth scales complete reference build, rebuild, qualification and cut peaks. Preparation is measured for this input. Sequential phases use their maximum, then 25% margin. With partial sources this is an early screening forecast, not full-region admission, measured graph RAM, a rigorous lower bound, or a memory guarantee."}


def write_plan(data, destination):
    load = lambda path: json.loads(path.read_text())
    manifest_path, cut_path = data / CURRENT / "manifest.json", data / CUTS / "report.json"
    manifest, cuts = load(manifest_path), load(cut_path)
    records_path = data / CUTS / "cut-nodes.json"
    expected = cuts["artifacts"]["cut-nodes.json"]
    if (cuts["graphIdentity"] != manifest["graphIdentity"] or
            cuts["sourceManifestSha256"] != checksum(manifest_path) or
            {"bytes": records_path.stat().st_size, "sha256": checksum(records_path)} != expected or
            cuts["nodesWithoutBoundaryLinks"] != 0):
        raise ValueError("Cut inventory is not bound to the qualified graph/source links")
    records = load(records_path)
    result = frontier(records, manifest["profile"]["bbox"])
    if result["cutNodesAccounted"] != cuts["auditedCutNodes"] or result["cutHistoryStatesAccounted"] != cuts["cutStates"]:
        raise ValueError("Incomplete cut/history inventory")
    report = {"graphIdentity": manifest["graphIdentity"], "frontier": result,
              "manifestSha256": checksum(manifest_path), "cutReportSha256": checksum(cut_path),
              "cutNodesArtifact": expected, "planningScriptSha256": checksum(Path(__file__)),
              "frontierHelperSha256": checksum(Path(__file__).with_name("two_hour_frontier.py")),
              "publicApiCalls": 0, "coverageVerified": False, "newGraphBuilt": False}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("data/coverage-pilot/six-hour-plan-v1/plan.json"))
    args = parser.parse_args()
    print(json.dumps(write_plan(args.data, args.output), indent=2))
