"""Admission to a separate capped experiment, not production coverage qualification."""


def evaluate(preparation, imported, calibration, candidate, factor=1.25):
    cap = 4 * 1024 ** 3
    ratios = {key: candidate[key] / calibration[key] for key in ("sourceNodes", "sourceWays", "sourceRelations", "wayEligibleDirectedSegments", "historyPrefixCeiling", "candidateViaWayRules")}
    ratios.update({"roadCeilingToBuiltRoads": candidate["roadStatesUpperBound"] / imported["roads"],
                   "historyCeilingToBuiltStates": candidate["historyStatesUpperBound"] / imported["states"]})
    scale = max(ratios.values())
    peaks = {}
    pressure = False
    for name, report in (("preparation", preparation), ("import", imported)):
        rows = report["resourceCheckpoints"].values()
        for row in rows:
            if int(row["memory.max"]) != cap or row["memory.swap.max"] != "0" or row["memory.swap.peak"] != "0":
                raise ValueError("Admission requires the recorded 4 GiB/no-swap policy")
            if any(int(row["memory.events"][event]) for event in ("oom", "oom_kill", "oom_group_kill")): raise ValueError("OOM evidence cannot be admitted")
            pressure |= int(row["memory.events"]["max"]) > 0
        peaks[name] = max(int(row["memory.peak"]) for row in report["resourceCheckpoints"].values())
    scaled_import = peaks["import"] * scale
    estimate = round(max(peaks["preparation"], scaled_import) * factor)
    parity = preparation["xmlByteIdentical"] and bool(imported["identicalArtifactSha256"])
    admitted = parity and not pressure and estimate < cap
    return {"decision": "eligible-for-separate-capped-import" if admitted else "hold", "cappedImportEligible": admitted,
            "ratios": ratios, "scalingRatio": scale, "observedPeaksBytes": peaks, "scaledImportPeakBytes": round(scaled_import),
            "headroomFactor": factor, "wholeWorkloadEstimateWithHeadroomBytes": estimate, "capBytes": cap,
            "limitPressure": pressure, "exactSourceAndGraphParity": parity, "newGraphQualified": False, "coverageVerified": False,
            "scope": "Heuristic scales measured whole-container import/export by the largest corresponding input/road/history ratio, then takes the maximum with measured candidate preparation and adds margin. Phases are sequential, not summed. Topology/fallback complexity, file cache and runtime noise can change scaling; this authorizes only an isolated capped attempt with preserved failures."}
