"""Whole-container gate for a separate cached one-hour coverage experiment."""

import math


def peak(report):
    rows = report["resourceCheckpoints"].values()
    pressure = False
    largest = 0
    for row in rows:
        if int(row["memory.max"]) != 4 * 1024 ** 3 or any(row[key] != "0" for key in
                ("memory.swap.max", "memory.swap.current", "memory.swap.peak")):
            raise ValueError("Require the recorded 4 GiB/no-swap policy")
        if any(int(row["memory.events"][key]) for key in ("oom", "oom_kill", "oom_group_kill")):
            raise ValueError("An OOM workload cannot be admitted")
        pressure |= int(row["memory.events"]["max"]) > 0
        largest = max(largest, int(row["memory.peak"]))
    if not largest: raise ValueError("Missing measured peak")
    return largest, pressure


def evaluate(calibration, candidate, counts, built, rebuilt, qualified):
    ratios = {key: counts[key] / calibration["candidate"][key] for key in
              ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")}
    ratios.update({"roadCeilingToBuiltRoads": counts["roadStatesUpperBound"] / built["roads"],
                   "historyCeilingToBuiltStates": counts["historyStatesUpperBound"] / built["states"]})
    scale = max(ratios.values())
    observed = {name: peak(report) for name, report in (("calibrationPreparation", calibration), ("candidatePreparation", candidate),
                ("build", built), ("rebuild", rebuilt), ("qualification", qualified))}
    pressure = any(value[1] for value in observed.values())
    measured = {key: value[0] for key, value in observed.items()}
    estimates = {"preparation": max(measured["calibrationPreparation"], measured["candidatePreparation"]),
                 "importExport": math.ceil(max(measured["build"], measured["rebuild"]) * scale),
                 "qualification": math.ceil(measured["qualification"] * scale)}
    estimate = math.ceil(max(estimates.values()) * 1.25)
    parity = calibration["xmlByteIdentical"] and len(calibration["fixtures"]) == 6 and all(row["graphAndAuditIdentical"] for row in calibration["fixtures"]) and qualified["functionalSummaryIdentical"]
    admitted = parity and not pressure and estimate < 4 * 1024 ** 3
    return {"decision": "eligible-for-separate-capped-build-and-qualification" if admitted else "hold",
            "cappedExperimentEligible": admitted, "ratios": ratios, "scalingRatio": scale, "observedPeaksBytes": measured,
            "estimatedPhasePeaksBytes": estimates, "headroomFactor": 1.25, "wholeWorkloadEstimateWithHeadroomBytes": estimate,
            "capBytes": 4 * 1024 ** 3, "limitPressure": pressure, "sourceAndOracleParity": parity,
            "newGraphBuilt": False, "coverageVerified": False,
            "scope": "Largest corresponding source/road/history ratio scales the worst measured build/rebuild and lean qualification container peaks. Sequential phases take a maximum, not a sum; measured preparation is included, then 25% margin. This is a heuristic for an isolated capped attempt, not a memory bound or a geographic-coverage claim."}
