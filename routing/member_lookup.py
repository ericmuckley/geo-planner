"""Restriction-member lookup with a global, per-way duplicate-geometry scan.

build_base emits roads in ascending way order. Keep only one way's geometry
keys for duplicate detection, but retain selected member keys for resolution.
"""

import time


def road_lookup(base, member_ways):
    started = time.perf_counter()
    selected = set(member_ways)
    lookup, seen = {}, set()
    previous = None
    duplicates = largest = member_roads = 0
    roads = base.roads
    for index, (way, tail, head) in enumerate(zip(roads.ways, roads.tails, roads.heads)):
        if previous != way:
            if previous is not None and way < previous:
                raise ValueError("Member lookup requires ascending way order")
            seen.clear()
            previous = way
        pair = (tail, head)
        if pair in seen: duplicates += 1
        else: seen.add(pair)
        largest = max(largest, len(seen))
        if way in selected:
            lookup[(way, tail, head)] = index
            member_roads += 1
    return lookup, bool(duplicates), {
        "candidateWayCount": len(selected), "retainedKeys": len(lookup),
        "memberRoadsScanned": member_roads, "totalRoads": len(roads),
        "duplicateRoads": duplicates, "maxWayKeys": largest,
        "scanMs": (time.perf_counter() - started) * 1000,
    }


def resolve(rule, ways, base, lookup, duplicate_geometry):
    members = [ways.get(way, []) for way in rule["ways"]]
    if any(len(nodes) < 2 or len(set(nodes)) != len(nodes) for nodes in members):
        raise ValueError("missing, closed or repeated-node member way")
    joins = []
    for left, right in zip(members, members[1:]):
        shared = set(left).intersection(right)
        if len(shared) != 1:
            raise ValueError("ambiguous/disconnected member join")
        join = next(iter(shared))
        if join not in (left[0], left[-1]) or join not in (right[0], right[-1]):
            raise ValueError("member join is not an endpoint")
        joins.append(join)
    triples = []
    first = members[0]
    triples.append((rule["ways"][0], first[1] if first[0] == joins[0] else first[-2], joins[0]))
    for index, nodes in enumerate(members[1:-1], 1):
        if joins[index - 1] == joins[index]:
            raise ValueError("via way has identical entry and exit")
        directed = nodes if nodes[0] == joins[index - 1] else list(reversed(nodes))
        triples.extend((rule["ways"][index], tail, head) for tail, head in zip(directed, directed[1:]))
    last = members[-1]
    triples.append((rule["ways"][-1], joins[-1], last[1] if last[0] == joins[-1] else last[-2]))
    if duplicate_geometry:
        raise ValueError("Duplicate directed road geometry")
    if any(triple not in lookup for triple in triples):
        raise ValueError("directed member segment absent after access/coverage/fallback exclusions")
    roads = [lookup[triple] for triple in triples]
    if any(not any(target == right for target, _ in base.adjacency[left]) for left, right in zip(roads, roads[1:])):
        raise ValueError("member path blocked by existing node/access rules")
    return {**rule, "roads": roads, "roadIds": [base.roads[index]["id"] for index in roads], "joinNodes": joins}

