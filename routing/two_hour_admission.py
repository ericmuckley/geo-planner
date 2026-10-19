"""Whole-workload resource forecast; source-envelope clipping remains explicit."""

import math

from hour_admission import peak


def evaluate(calibration, candidate, counts, built, rebuilt, qualified, native, cuts, frontier):
    ratios = {key: counts[key] / calibration["candidate"][key] for key in
              ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")}
    ratios.update({"roadCeilingToBuiltRoads": counts["roadStatesUpperBound"] / built["roads"],
                   "historyCeilingToBuiltStates": counts["historyStatesUpperBound"] / built["states"]})
    scale = max(1, *ratios.values())
    observed = {name: peak(report) for name, report in (("calibrationPreparation", calibration), ("candidatePreparation", candidate),
                ("build", built), ("rebuild", rebuilt), ("qualification", qualified), ("inventory", cuts))}
    measured = {key: value[0] for key, value in observed.items()}
    pressure = any(value[1] for value in observed.values())
    estimates = {"preparation": max(measured["calibrationPreparation"], measured["candidatePreparation"]),
                 "importExport": math.ceil(max(measured["build"], measured["rebuild"]) * scale),
                 "qualification": math.ceil(measured["qualification"] * scale), "inventory": math.ceil(measured["inventory"] * scale)}
    estimate = math.ceil(max(estimates.values()) * 1.25)
    states = built["states"]
    parity = (calibration["xmlByteIdentical"] and len(calibration["fixtures"]) == 6 and all(row["graphAndAuditIdentical"] for row in calibration["fixtures"])
              and qualified["costComparisons"] == states * 5 and qualified["boundedCostComparisons"] == states * 40
              and qualified["interiorDestinationComparisons"] == native["interiorDestinationComparisons"] == 2
              and native["costComparisons"] == states * 45 and native["membershipComparisons"] == states * 40
              and qualified["graphIdentity"] == native["graphIdentity"] == cuts["graphIdentity"] == built["graphIdentity"])
    admitted = parity and not pressure and estimate < 4 * 1024 ** 3
    return {"decision": ("eligible-for-separate-bounded-source-experiment" if admitted else "hold"),
            "cappedExperimentEligible": admitted, "ratios": ratios, "scalingRatio": scale, "observedPeaksBytes": measured,
            "estimatedPhasePeaksBytes": estimates, "headroomFactor": 1.25, "wholeWorkloadEstimateWithHeadroomBytes": estimate,
            "capBytes": 4 * 1024 ** 3, "limitPressure": pressure, "sourceAndOracleParity": parity,
            "sourceEnvelopeContained": frontier["envelopeContainedInParent"], "sourceEnvelopeClippedSides": frontier["clippedSides"],
            "newGraphBuilt": False, "coverageVerified": False,
            "scope": "Largest source/road/history ratio (at least one) scales worst measured build/rebuild, qualification and inventory peaks; measured preparation included; sequential maximum plus 25%. Heuristic, not a bound. Source-envelope clipping and parent road gaps remain separate from resource admission; no complete two-hour coverage claim."}
