"""Reject ambiguous geometry only in the restriction that references it."""

import time

from member_lookup import resolve as resolve_member


POLICY_ID = "member-scoped-geometry-v1"


def road_lookup(base, member_ways):
    started = time.perf_counter()
    selected, lookup, seen, ambiguous = set(member_ways), {}, set(), set()
    previous = None
    duplicates = largest = member_roads = 0
    examples = []
    roads = base.roads
    for index, (way, tail, head) in enumerate(zip(roads.ways, roads.tails, roads.heads)):
        if previous != way:
            if previous is not None and way < previous: raise ValueError("Member lookup requires ascending way order")
            seen.clear()
            previous = way
        pair = (tail, head)
        if pair in seen:
            duplicates += 1
            ambiguous.add(way)
            if len(examples) < 16:
                examples.append({"way": way, "from": tail, "to": head, "segment": roads.segments[index],
                                 "direction": "r" if roads.directions[index] else "f", "restrictionMember": way in selected})
        else: seen.add(pair)
        largest = max(largest, len(seen))
        if way in selected:
            lookup[(way, tail, head)] = index
            member_roads += 1
    return lookup, ambiguous, {"candidateWayCount": len(selected), "retainedKeys": len(lookup),
        "memberRoadsScanned": member_roads, "totalRoads": len(roads), "duplicateRoads": duplicates,
        "ambiguousWayIds": sorted(ambiguous), "duplicateExamples": examples, "maxWayKeys": largest,
        "policy": POLICY_ID, "scanMs": (time.perf_counter() - started) * 1000}


def resolve(rule, ways, base, lookup, ambiguous_ways):
    # Keep the frozen member/topology/access validations and their error priority.
    return resolve_member(rule, ways, base, lookup, any(way in ambiguous_ways for way in rule["ways"]))
