"""Join original selection facts to current closure contributors, never grant access."""
from collections import Counter


def reconcile_closures(original, converted, current):
    assert all(type(i) is int and 0 < i < 2**63 for i in converted | current)
    remaining = {}
    for identity, contributors in original.items():
        assert str(int(identity)) == identity and int(identity) > 0
        assert contributors == sorted(set(contributors)) and all(type(i) is int and i > 0 for i in contributors)
        kept = [i for i in contributors if i not in converted]
        if kept: remaining[identity] = kept
    assert {int(k) for k in remaining} == current, 'Every current closure independently replays all unconverted contributors'
    return remaining


def classify_inventory(evidence, current, contributors, relations):
    counts = Counter(); reasons = Counter(); lane_shapes = Counter(); rows = {}
    for key, source in evidence.items():
        identity = source['sourceWay']
        assert str(identity) == key and source['rawWayKnown'] and source['rawTags'] is not None
        reason = source['currentRawPolicy']['reason']
        assert source['baseEligible'] == (reason is None)
        closed = identity in current
        closing = contributors.get(key, [])
        assert bool(closing) == closed
        kinds = sorted({relations[i]['closureKind'] for i in closing})
        assert not closing or all(key in relations[i]['closedWays'] for i in closing)
        excluded = reason is not None or closed
        assert excluded or source['baseEligible'] and source['finalFallbackClosed']
        category = 'retained-now' if not excluded else 'base-ineligible' if reason is not None else 'base-eligible-fallback-closed'
        counts[category] += 1
        if reason is not None: reasons[reason] += 1
        tags = source['rawTags']
        lane_keys = sorted(k for k in tags if k.startswith(('access','vehicle','motor','oneway')) and (k.endswith(':lanes') or ':lanes:' in k))
        if reason == 'lane-access':
            lane_shapes['only-oneway-vectors' if lane_keys and all(k.startswith('oneway') for k in lane_keys) else 'access-or-mixed-vectors'] += 1
        rows[key] = dict(sourceWay=identity,baseEligible=source['baseEligible'],baseReason=reason,
                         originallyFallbackClosed=source['finalFallbackClosed'],currentFallbackClosed=closed,
                         currentExcluded=excluded,category=category,closingRelationIds=closing,closingKinds=kinds,
                         laneStatus=source['laneStatus'],laneKeys=lane_keys)
    assert sum(counts.values()) == len(evidence) == len(rows)
    return rows, dict(counts), dict(reasons), dict(lane_shapes)
