"""Compose a narrow incomplete-maneuver correction with qualified node guards."""
from array import array
from dataclasses import asdict

from coarse_osm_car_passable_barriers_v1 import graph_node_decision
from coarse_osm_incomplete_node_restrictions_v1 import classify, remaining_contributors
from coarse_timing_input import require


def rules_from_metadata(rows):
    rules = {}
    previous = 0
    for row in rows:
        rule = classify(row['source'])['rule']
        require(rule is not None and previous < rule.identity and asdict(rule) == row['derived'],
                'Complete original and derived incomplete source records')
        rules[rule.identity] = rule
        previous = rule.identity
    return rules


def validate(flags, mapping, evidence, permutation):
    require(isinstance(flags, bytes) and flags and all(v < 8 for v in flags), 'Complete current node-flag bytes')
    require(len(permutation) == len(flags), 'Complete native-to-spatial permutation')
    seen = bytearray(len(flags))
    for vertex in permutation:
        require(type(vertex) is int and 0 <= vertex < len(flags) and not seen[vertex], 'Every spatial vertex has one native anchor')
        seen[vertex] = 1
    by_vertex, identities = {}, set()
    for row in mapping:
        vertex, anchor = row['vertex'], row['sourceAnchor']
        identity = str(row['sourceNodeId'])
        require(type(vertex) is int and type(anchor) is int and 0 <= anchor < len(flags)
                and permutation[anchor] == vertex and vertex not in by_vertex and identity not in identities,
                'Exact prior source-ID mapping on the fresh unchanged-vertex permutation')
        require(identity in evidence and row['flags'] & 1 and row['flags'] < 8, 'Every original blocker has known source evidence')
        source = evidence[identity]
        old = graph_node_decision(source['rawTags'], source['restrictionContributorIds'])
        expected = row['flags'] if old['blocked'] else row['flags'] & ~1
        require(flags[vertex] == expected and bool(flags[vertex] & 2) == old['base']['signal'],
                'Exact current passable policy and original signal/reversal bits')
        by_vertex[vertex] = row
        identities.add(identity)
    require(identities == set(evidence), 'Every original blocked source tag replayed once')
    require(all(not value & 1 or vertex in by_vertex for vertex, value in enumerate(flags)),
            'No unexplained current blocked vertex')
    return by_vertex


def build(flags, mapping, evidence, permutation, incomplete):
    by_vertex = validate(flags, mapping, evidence, permutation)
    proposed = bytearray(flags)
    changes = []
    for vertex, row in sorted(by_vertex.items()):
        identity = str(row['sourceNodeId'])
        source = evidence[identity]
        remaining = remaining_contributors(int(identity), source['restrictionContributorIds'], incomplete)
        decision = graph_node_decision(source['rawTags'], remaining)
        if flags[vertex] & 1 and not decision['blocked']:
            require(source['restrictionContributorIds'] and not remaining and not decision['base']['blocked'],
                    'An opening removes only incomplete contributors and no direct guard')
            proposed[vertex] &= ~1
            changes.append({'vertex': vertex, 'sourceNodeId': identity,
                            'removedContributorIds': source['restrictionContributorIds'],
                            'oldFlags': flags[vertex], 'newFlags': proposed[vertex]})
    return bytes(proposed), changes


def audit(original, proposed, mapping, evidence, permutation, incomplete):
    by_vertex = validate(original, mapping, evidence, permutation)
    require(isinstance(proposed, bytes) and len(proposed) == len(original), 'Same complete node shape')
    changed = array('I')
    for vertex, (before, after) in enumerate(zip(original, proposed)):
        expected = before
        if vertex in by_vertex:
            identity = str(by_vertex[vertex]['sourceNodeId'])
            source = evidence[identity]
            require(all(incomplete[relation].via_node == int(identity)
                        for relation in source['restrictionContributorIds'] if relation in incomplete),
                    'Every omitted source relation names this same node')
            remaining = [identity for identity in source['restrictionContributorIds'] if identity not in incomplete]
            if not graph_node_decision(source['rawTags'], remaining)['blocked']:
                expected &= ~1
        require(after == expected, 'Every proposed flag independently recomputes from original tags and retained causes')
        if before != after:
            require(before & 1 and after == before & ~1, 'Only a blocker bit can clear')
            changed.append(vertex)
    return {'allVertexFlagsIndependentlyCompared': len(original), 'openedVertices': len(changed),
            'changedVertices': changed, 'remainingBlockedVertices': sum(bool(v & 1) for v in proposed),
            'signalsAndReversalBitsExact': all(a & 6 == b & 6 for a, b in zip(original, proposed)),
            'everyOldOpenVertexExact': all(a == b for a, b in zip(original, proposed) if not a & 1),
            'everyDirectGuardAndOtherContributorRetained': True}
