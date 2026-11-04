"""Independent exhaustive typed audit of entry resolution; no native execution."""
from array import array
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
import struct

from coarse_osm_car_packed_audit_v1 import rows

ARC = struct.Struct('<IIIIIb3sQ')


def fixed(path, shape, maximum):
    path = Path(path)
    assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216
    raw = path.read_bytes()
    assert len(raw) % shape.size == 0 and len(raw)//shape.size <= maximum
    return shape.iter_unpack(raw)


def audit(source, rules, fallback, output, dimensions, native_counts, *, baseline_post, check=lambda: None):
    source, output = Path(source), Path(output)
    way_count, vertices, pre, rule_count, fallback_count = dimensions
    assert 0 < way_count <= 8000000 and 0 < vertices <= 0xffffff and 0 <= pre <= 0xffffff
    assert 0 <= rule_count <= 100000 and 0 <= fallback_count <= 200000
    ways = array('Q')
    for row in rows(source, 'ways', struct.Struct('<QddII')):
        identity = row[0]
        assert 0 < identity < 2**63 and (not ways or ways[-1] < identity)
        ways.append(identity)
    assert len(ways) == way_count
    heads, tails = array('I'), array('I')
    offsets = array('I', [0])*(way_count+1)
    cursor = 0
    previous = None
    for i, (tail, head, way, first, last, direction, padding, ms) in enumerate(rows(source, 'arcs', ARC)):
        assert i < pre and tail < vertices and head < vertices and way < way_count and first < last
        assert direction in (-1, 1) and padding == b'\0'*3 and 0 < ms <= 0xffffffff*125
        key = way, first, last, -direction
        assert previous is None or previous < key
        previous = key
        while cursor <= way:
            offsets[cursor] = i
            cursor += 1
        heads.append(head)
        tails.append(tail)
        if i % 16384 == 0:
            check()
    assert len(heads) == pre
    while cursor <= way_count:
        offsets[cursor] = pre
        cursor += 1
    original = array('Q', (r[0] for r in rows(source, 'closures', struct.Struct('<Q'))))
    assert len(original) <= 200000 and all(a < b for a, b in zip(original, original[1:]))
    assert all(0 < identity < 2**63 for identity in original)
    old = set(original)
    initial = [r[0] for r in fixed(fallback, struct.Struct('<Q'), 200000)]
    assert len(initial) == fallback_count and all(a < b for a, b in zip(initial, initial[1:]))
    closed = set(initial)
    assert closed <= old
    def ordinal(identity):
        at = bisect_left(ways, identity)
        return at if at < len(ways) and ways[at] == identity else None
    def retained(blocked):
        count = pre
        for identity in blocked:
            at = ordinal(identity)
            if at is not None:
                count -= offsets[at+1]-offsets[at]
        return count
    assert retained(old) == baseline_post
    decisions = list(fixed(output/'decisions.bin', struct.Struct('<QII'), 100000))
    assert len(decisions) == rule_count
    expected_pairs = set()
    resolved = missing = no_join = raw_pair_total = seen = prior_id = 0
    for identity, from_way, via_way, to_way in fixed(rules, struct.Struct('<QQQQ'), 100000):
        check()
        assert prior_id < identity < 2**63 and from_way != via_way != to_way
        assert {from_way, via_way, to_way} <= old
        prior_id = identity
        a, b, c = [ordinal(n) for n in (from_way, via_way, to_way)]
        pair_count = 0
        if any(i is None or offsets[i] == offsets[i+1] for i in (a, b, c)):
            status = 1
            missing += 1
        else:
            assert offsets[a+1]-offsets[a]+offsets[b+1]-offsets[b] <= 200000
            # Bounded per-rule junction map, not a country node dictionary.
            by_tail = defaultdict(list)
            for j in range(offsets[b], offsets[b+1]):
                by_tail[tails[j]].append(j)
            for i in range(offsets[a], offsets[a+1]):
                for j in by_tail.get(heads[i], ()):
                    expected_pairs.add((i, j))
                    pair_count += 1
            if pair_count:
                status = 0
                resolved += 1
            else:
                status = 2
                no_join += 1
        if status:
            closed.update((from_way, via_way, to_way))
        raw_pair_total += pair_count
        assert raw_pair_total <= 2000000
        assert seen < len(decisions) and decisions[seen] == (identity, status, pair_count)
        seen += 1
    assert seen == rule_count
    actual_closed = array('Q', (r[0] for r in fixed(output/'closures-0000.bin', struct.Struct('<Q'), 200000)))
    assert actual_closed == array('Q', sorted(closed)) and closed <= old
    actual_pairs = list(fixed(output/'entry-pairs-pre.u32', struct.Struct('<II'), 2000000))
    assert actual_pairs == sorted(expected_pairs)
    assert all(heads[a] == tails[b] for a, b in actual_pairs)
    post = retained(closed)
    expected = [rule_count, resolved, missing, no_join, len(old), len(closed), len(expected_pairs), pre, post]
    assert expected == native_counts and post >= baseline_post
    return {'status': 'independent_complete_entry_resolution_audit_passed',
            'waysChecked': way_count, 'preArcsChecked': pre, 'candidateRulesChecked': seen,
            'decisionsChecked': len(decisions), 'entryPairsChecked': len(actual_pairs),
            'originalClosureIdsChecked': len(old), 'overrideClosureIdsChecked': len(closed),
            'originalPostArcs': baseline_post, 'candidatePostArcs': post,
            'allPairsUseActualSourceNodeIdentity': True, 'fallbackUnionExact': True,
            'nativeLibraryExecutions': 0, 'sourcePbfReads': 0,
            'scope': 'Every metadata decision/pair/closure and pre-arc field checked with dense typed source arrays and bounded per-rule maps. Costs are range checked; original geometry/cost semantic seals remain inherited. No graph/package/ETA admission.'}
