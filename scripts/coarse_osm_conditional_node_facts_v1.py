"""Replace qualified whole-way contributors with all-state junction bans."""
from collections import defaultdict
from dataclasses import asdict
import struct

from analyze_osm_source_gap_closures_v2 import contribution
from coarse_osm_conditional_node_inventory_v1 import closure_unions
from coarse_osm_conditional_node_turns_v2 import classify
from coarse_osm_passable_node_overlay_v1 import audit_overlay, build_overlay
from coarse_timing_input import require

TURN = struct.Struct('<QQQQB7s')
KIND = {'no_left_turn': 0, 'no_right_turn': 1, 'no_straight_on': 2, 'no_u_turn': 3}


def relation_overlay(elements, single, multi, old_closed, metadata, descriptors):
    """Reconstruct the local union before removing only supported contributors."""
    candidates = {}
    for row in metadata:
        rule = classify(row['source'])['rule']
        require(rule is not None, 'Original conditional metadata still qualifies')
        derived = {k: str(v) if type(v) is int else v for k, v in asdict(rule).items()}
        require(derived == row['derived'] and rule.identity not in candidates,
                'Unique original metadata and exact derived source IDs')
        candidates[rule.identity] = (row['source'], rule)
    ports = {}
    for row in descriptors:
        identity = int(row['sourceRelationId'])
        require(identity in candidates and identity not in ports, 'Unique complete qualified source descriptors')
        rule = candidates[identity][1]
        require((row['fromWayId'], row['viaNodeId'], row['toWayId'], row['kind']) ==
                (str(rule.from_way), str(rule.via_node), str(rule.to_way), rule.kind),
                'Physical source descriptor matches original relation')
        if row['status'] == 'source-ports-supported':
            require(row['incomingPreArcIds'] and row['outgoingPreArcIds'], 'Both directed ports required')
        ports[identity] = row
    require(set(ports) == set(candidates), 'Every metadata candidate retains a port result')
    closing = []
    added = {}
    seen_single, seen_multi = set(), set()
    previous = count = 0
    for element in elements:
        identity = element['id']
        require(type(identity) is int and previous < identity, 'Complete sorted raw unsupported relations')
        previous = identity
        count += 1
        ways, kind, branch = contribution(element, single, multi)
        if branch == 'single':
            seen_single.add(identity)
        elif branch == 'multi':
            seen_multi.add(identity)
        if ways:
            closing.append({'sourceRelation': identity, 'closedWays': ways})
        if identity in candidates and ports[identity]['status'] == 'source-ports-supported':
            original, rule = candidates[identity]
            require(element == original and branch is None and kind == 'constant-conditional'
                    and set(ways) == {rule.from_way, rule.to_way},
                    'Only the exact original conditional whole-way contribution changes')
            added[identity] = (identity, rule.from_way, rule.via_node, rule.to_way, KIND[rule.kind], bytes(7))
    require(seen_single == set(single) and seen_multi == set(multi), 'Every current single/multi decision retained')
    old, proposed = closure_unions(closing, set(added))
    require(old == set(old_closed), 'Entire current local closure union independently reconstructed')
    # A second, way-centric replay preserves shared and unrelated contributors.
    contributors = defaultdict(set)
    for row in closing:
        for way in row['closedWays']:
            contributors[way].add(row['sourceRelation'])
    expected = {way for way, relations in contributors.items() if relations - added.keys()}
    require(expected == proposed and proposed <= old, 'Every independent contributor remains')
    return {'added': added, 'closed': proposed, 'rawRelations': count,
            'originalClosedWays': len(old), 'convertedRelations': len(added),
            'sourceSupportedOutsideLocalMetadata': sum(row['status'] == 'source-ports-supported'
                                                      and identity not in added for identity, row in ports.items()),
            'reopenedWayIds': sorted(old - proposed),
            'sharedClosedWaysRetained': sum(bool(ids & added.keys()) and bool(ids - added.keys())
                                          for ids in contributors.values())}


def merge_turns(original, additions):
    """Original records remain byte-exact, including their source relation order."""
    require(isinstance(original, bytes) and len(original) % TURN.size == 0, 'Complete original turn bytes')
    for identity, row in additions.items():
        require(len(row) == 6 and type(identity) is int and row[0] == identity
                and all(type(n) is int and 0 < n < 2**63 for n in row[:4])
                and row[1] != row[3] and row[4] in range(4) and row[5] == bytes(7),
                'Exact supported all-state typed turn shape')
    output = bytearray()
    ordered = iter(sorted(additions.items()))
    pending = next(ordered, None)
    previous = 0
    for at in range(0, len(original), TURN.size):
        raw = original[at:at + TURN.size]
        row = TURN.unpack(raw)
        require(previous < row[0] < 2**63 and all(0 < n < 2**63 for n in row[1:4])
                and row[4] < 10 and row[5] == bytes(7), 'Original turn identity/order/shape')
        previous = row[0]
        while pending is not None and pending[0] < row[0]:
            output.extend(TURN.pack(*pending[1]))
            pending = next(ordered, None)
        require(pending is None or pending[0] != row[0], 'Converted IDs must be absent from existing typed turns')
        output.extend(raw)
    while pending is not None:
        output.extend(TURN.pack(*pending[1]))
        pending = next(ordered, None)
    proposed = bytes(output)
    audit_turns(original, proposed, additions)
    return proposed


def audit_turns(original, proposed, additions):
    require(len(proposed) == len(original) + TURN.size * len(additions), 'Exact new turn byte count')
    old = dict((r[0], r) for r in TURN.iter_unpack(original))
    actual = list(TURN.iter_unpack(proposed))
    require(all(a[0] < b[0] for a, b in zip(actual, actual[1:])), 'New turns sorted/unique')
    require(set(old).isdisjoint(additions) and len(actual) == len(old) + len(additions), 'Exact disjoint turn identities')
    for row in actual:
        require(row == (old[row[0]] if row[0] in old else additions[row[0]]), 'Every old/new typed turn independently compared')
    require({r[0] for r in actual} == old.keys() | additions.keys(), 'No missing or invented turn')
    return {'oldSourceTurnsByteExact': len(old), 'newAllStateJunctionBans': len(additions),
            'allSourceTurnsIndependentlyCompared': len(actual)}


def native_passable_flags(flags, mapping, evidence, ids, anchors):
    """Reapply the qualified node rule in native anchor order, never spatial order."""
    rebased = []
    selected = {}
    for row in mapping:
        anchor = row['sourceAnchor']
        require(type(anchor) is int and 0 <= anchor < len(anchors)
                and anchors[anchor] == row['sourceNodeIndex']
                and ids[row['sourceNodeIndex']] == int(row['sourceNodeId']),
                'Exact native node/anchor permutation before flag correction')
        identity = str(row['sourceNodeId'])
        require(identity in evidence and identity not in selected, 'Every actual blocked source node has known tags')
        rebased.append(row | {'vertex': anchor})
        selected[identity] = evidence[identity]
    proposed, changed = build_overlay(flags, rebased, selected)
    proof = audit_overlay(flags, proposed, rebased, selected)
    require(proof['changedVertices'] == [row['vertex'] for row in changed], 'Independent native flag correction replay')
    return proposed, proof
