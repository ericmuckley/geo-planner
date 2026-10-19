"""Versioned qualification with virtual sink storage and the frozen full-field oracle.

Same routing algorithms and comparisons as lean_checks. Restrict the road-ID lookup
to the fixture targets, stream field output, compare bounded labels without a copy,
and release completed label fields. The frozen module remains unchanged.
"""

from fractions import Fraction
import hashlib
import math
import struct
import time

from cache_lifetime import write_blocks
from maneuver_graph import interior_destination, replay, source_seeds
from virtual_sink import destination_oracle
from native_support import UINT64_MAX, membership_bytes
from regional_support import route_to_interior, snap_attachments
from crossing_audit import route_evidence
from native_support import decode_labels
from state_graph import dijkstra
from queue_oracle import bellman_ford


def label_blocks(labels, block_size=4096):
    block = []
    for value in labels:
        block.append(UINT64_MAX if value == math.inf else value)
        if len(block) == block_size:
            yield struct.pack(f"<{len(block)}Q", *block)
            block.clear()
    if block: yield struct.pack(f"<{len(block)}Q", *block)


def bounded_equal(actual, exact, budget):
    return len(actual) == len(exact) and all(value == (reference if reference <= budget else math.inf) for value, reference in zip(actual, exact))


def qualify(output, graph, audit, profile, old_summary, examples, port_incoming, port_outgoing):
    wanted = set(old_summary["alternativeRoadIds"].values())
    by_id = {road["id"]: index for index, road in enumerate(graph.base.roads) if road["id"] in wanted}
    rules = {rule["id"]: rule for rule in graph.patterns}
    maneuvers = []
    for previous in old_summary["sourceSamples"]:
        original = previous["restriction"]
        rule = rules[original["id"]]
        if rule["roadIds"] != original["roadIds"]: raise ValueError("Qualified maneuver geometry changed")
        other_index = by_id[old_summary["alternativeRoadIds"][str(original["id"])]]
        blocked, allowed = replay(graph, rule["roads"]), replay(graph, [other_index] + rule["roads"][1:])
        if blocked["allowed"] or not allowed["allowed"]: raise ValueError("Prior maneuver decision changed")
        maneuvers.append({"restriction": rule, "alternativeRoadId": graph.base.roads[other_index]["id"], "blocked": blocked, "allowed": allowed})
    origins = []
    for origin in profile["origins"]:
        starts, seeds, snap = snap_attachments(graph, [origin["lon"], origin["lat"]], profile["sourceSnapMaxMeters"])
        origins.append({"id": origin["id"], "starts": starts, "seeds": seeds, "snap": snap})
    permitted = [(left, right) for left in port_incoming for right in port_outgoing if replay(graph, [left, right])["allowed"]]
    left, port_target = permitted[0]
    starts = [(left, Fraction(1, 2))]
    origins.append({"id": "port-incoming", "starts": starts, "seeds": source_seeds(graph, starts), "snap": None})
    cut_nodes = set(audit["cutExitNodes"])
    cut_states = [index for index, state in enumerate(graph.states) if graph.base.roads[state["road"]]["to"] in cut_nodes]
    counts = {"costComparisons": 0, "boundedCostComparisons": 0, "interiorDestinationComparisons": 0}
    checks, routes, destinations, artifacts = [], [], [], []
    (output / "oracles").mkdir(exist_ok=True)
    for origin in origins:
        before = time.perf_counter()
        result = dijkstra(graph.adjacency, origin["seeds"])
        search_ms = (time.perf_counter() - before) * 1000
        before = time.perf_counter()
        exact = bellman_ford(graph.adjacency, origin["seeds"])
        oracle_ms = (time.perf_counter() - before) * 1000
        if result.labels != exact: raise ValueError("Dijkstra/Bellman-Ford disagree on v3")
        counts["costComparisons"] += len(exact)
        result.labels = ()
        name = f"oracles/{origin['id']}.u64le"
        write_blocks(output / name, label_blocks(exact))
        artifacts.append(name)
        boundary = min((exact[state] for state in cut_states), default=math.inf)
        budgets = []
        for budget in profile["budgetsMs"]:
            bounded = dijkstra(graph.adjacency, origin["seeds"], budget)
            if not bounded_equal(bounded.labels, exact, budget): raise ValueError("Bounded v3 costs disagree")
            counts["boundedCostComparisons"] += len(exact)
            budgets.append({"budgetMs": budget, "reachableStates": bounded.settled_states, "scannedArcs": bounded.scanned_arcs,
                            "boundaryReachedWithinBudget": boundary <= budget, "membershipSha256": hashlib.sha256(membership_bytes(exact, budget)).hexdigest()})
            del bounded
        # A sink oracle independently verifies the real permitted crossing's interior target.
        if origin["id"] == "port-incoming":
            actual = interior_destination(graph, exact, port_target, Fraction(1, 2), origin["starts"])
            expected = destination_oracle(graph, origin["seeds"], port_target, Fraction(1, 2), origin["starts"])
            if actual != expected or not math.isfinite(actual): raise ValueError("Real port interior destination failed")
            destinations.append({"origin": origin["id"], "roadId": graph.base.roads[port_target]["id"], "fraction": "1/2", "costMs": actual})
            counts["interiorDestinationComparisons"] += 1
        if origin["snap"]:
            for destination in origins:
                if not destination["snap"] or destination["id"] == origin["id"]: continue
                candidates = []
                for road, fraction in destination["starts"]:
                    if not 0 < fraction < 1: raise ValueError("Sample requires a strict interior attachment")
                    trace = route_to_interior(graph, exact, origin["seeds"], origin["starts"], road, fraction)
                    if trace["costMs"] is not None: candidates.append((trace["costMs"], road, fraction, trace))
                if candidates:
                    cost, road, fraction, trace = min(candidates, key=lambda value: value[0])
                    routes.append({"origin": origin["id"], "destination": destination["id"], **trace,
                                   "targetRoadId": graph.base.roads[road]["id"], "targetFraction": str(fraction)})
                else:
                    routes.append({"origin": origin["id"], "destination": destination["id"], "costMs": None, "status": "unreachable in this imported model"})
        checks.append({"origin": origin["id"], "starts": [[road, str(fraction)] for road, fraction in origin["starts"]],
                       "seeds": origin["seeds"], "snap": origin["snap"], "fullReachableStates": result.settled_states,
                       "firstCutExitMs": boundary if math.isfinite(boundary) else None, "fullSearchMs": search_ms, "bellmanFordMs": oracle_ms, "budgets": budgets})
        print(f"Qualified {origin['id']}: {result.settled_states} reachable states; first cut {boundary} ms", flush=True)
        del result, exact
    return {"graphIdentity": graph.identity, "profile": profile, "baseRoads": len(graph.base.roads), "states": len(graph.states),
            "transitions": sum(map(len, graph.adjacency)), "viaWayRestrictions": len(graph.patterns), "barrierExamples": examples,
            "barrierDecisionCounts": audit["barrierPolicy"]["decisionCounts"], "sourceSamples": maneuvers,
            "origins": checks, "sampledRoutes": routes, "interiorDestinations": destinations, "oracleArtifacts": artifacts, **counts,
            "publicApiCalls": 0, "coverageVerified": False, "network": "none", "borderPolicy": profile["borderPolicy"]}



def diagnose_routes(output, graph, audit, summary):
    uncertainties = audit["sourceCrossingUncertainties"]
    origins = {row["origin"]: row for row in summary["origins"]}
    opened = {row["id"] for row in audit["barrierPolicy"]["decisions"] if row["open"] and not row["blockedByModel"]}
    for route in summary["sampledRoutes"]:
        route["accessEvidence"] = route_evidence(graph, origins[route["origin"]], route, uncertainties, opened)
    # Explicitly exercise the uncertain branch even when the fastest city route avoids it.
    origin = origins["tijuana"]
    road = next(index for index, road in enumerate(graph.base.roads) if road["id"] == "114198251:0:f")
    labels = decode_labels((output / "oracles/tijuana.u64le").read_bytes(), len(graph.states))
    actual = interior_destination(graph, labels, road, Fraction(1, 2), origin["starts"])
    expected = destination_oracle(graph, origin["seeds"], road, Fraction(1, 2), origin["starts"])
    if actual != expected or not math.isfinite(actual): raise ValueError("Uncertain crossing branch disagrees with sink oracle")
    route = {"origin": "tijuana", "destination": "uncertain-otay-way-interior",
             **route_to_interior(graph, labels, origin["seeds"], origin["starts"], road, Fraction(1, 2)),
             "targetRoadId": graph.base.roads[road]["id"], "targetFraction": "1/2"}
    route["accessEvidence"] = route_evidence(graph, origin, route, uncertainties, opened)
    if 114198251 not in route["accessEvidence"]["sourceUncertaintyWayIds"]: raise ValueError("Uncertain route warning lost")
    summary["uncertainBranchRoutes"] = [route]
    summary["sourceCrossingUncertainties"] = uncertainties
    summary["interiorDestinations"].append({"origin": "tijuana", "roadId": graph.base.roads[road]["id"], "fraction": "1/2", "costMs": actual})
    summary["interiorDestinationComparisons"] += 1
    summary["routeEligibilityVerified"] = False

