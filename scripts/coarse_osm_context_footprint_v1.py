"""Complete typed-fact context-state footprint; no coordinates or routing.

Only bounded rule/entry-pair records become Python objects. All country way
identities and arc counts remain dense typed arrays. Bounds count every via arc
and every possible to-way arc, without assuming that an exit is reachable.
"""
from array import array
from bisect import bisect_left
from collections import Counter, defaultdict
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, rows
from coarse_osm_entry_resolution_audit_v1 import fixed

PREFIX_COUNT = struct.Struct('<QQIIII')


def inventory(source, rule_path, decision_path, pair_path, dimensions, check=lambda: None):
    began = time.monotonic()
    way_count, vertices, pre_count, post_count, rule_count = dimensions
    assert 0 < way_count <= 8000000 and 0 < vertices <= 0xffffff
    assert 0 < post_count <= pre_count <= 0xffffff and 0 <= rule_count <= 100000
    source = Path(source)
    identities = array('Q')
    for identity, in rows(source, 'ways', struct.Struct('<Q24x')):
        assert 0 < identity < 2**63 and (not identities or identities[-1] < identity)
        identities.append(identity)
    assert len(identities) == way_count
    blocked = bytearray(way_count)
    closure_count = previous = 0
    def index(identity):
        at = bisect_left(identities, identity)
        return at if at < way_count and identities[at] == identity else None
    for identity, in rows(source, 'closures', struct.Struct('<Q')):
        assert previous < identity
        previous = identity
        closure_count += 1
        at = index(identity)
        if at is not None:
            blocked[at] = 1
    pairs = list(fixed(pair_path, struct.Struct('<II'), 200000))
    assert all(a < b for a, b in zip(pairs, pairs[1:]))
    selected = {n for pair in pairs for n in pair}
    assert all(n < pre_count for n in selected)
    selected_arcs = {}
    counts = array('I', [0])*way_count
    pre = retained = 0
    for tail, head, way, first, last, direction, padding, ms in rows(source, 'arcs', ARC):
        assert pre < pre_count and tail < vertices and head < vertices and way < way_count
        assert first < last and direction in (-1, 1) and padding == b'\0'*3
        assert 0 < ms <= 0xffffffff*125
        counts[way] += 1
        retained += not blocked[way]
        if pre in selected:
            selected_arcs[pre] = way, tail, head
        pre += 1
        if pre % 65536 == 0:
            check()
    assert pre == pre_count and retained == post_count and set(selected_arcs) == selected
    groups, group_rules = defaultdict(set), Counter()
    statuses = Counter()
    seen = prior_id = summed_rule_pairs = 0
    for rule, decision in zip(fixed(rule_path, struct.Struct('<QQQQ'), 100000),
                              fixed(decision_path, struct.Struct('<QII'), 100000), strict=True):
        identity, from_way, via_way, to_way = rule
        assert prior_id < identity and identity == decision[0]
        assert all(w > 0 for w in (from_way, via_way, to_way)) and via_way not in (from_way, to_way)
        prior_id = identity
        status, pair_count = decision[1:]
        assert status in (0, 2, 3)
        members = tuple(index(w) for w in (from_way, via_way, to_way))
        present = all(at is not None and counts[at] > 0 for at in members)
        if status == 3:
            assert not present and pair_count == 0
        else:
            assert present
            if status == 0:
                assert pair_count > 0
                key = members[:2]
                groups[key].add(members[2])
                group_rules[key] += 1
                summed_rule_pairs += pair_count
            else:
                assert pair_count == 0
                assert all(blocked[at] for at in members), 'No-join fallback closure lost'
        statuses[status] += 1
        seen += 1
        if seen % 1024 == 0:
            check()
    assert seen == rule_count and len(pairs) <= summed_rule_pairs
    active_pairs, dropped_pairs, group_triggers = 0, 0, Counter()
    for before, after in pairs:
        a, b = selected_arcs[before], selected_arcs[after]
        assert a[2] == b[1] and (a[0], b[0]) in groups
        if blocked[a[0]] or blocked[b[0]]:
            dropped_pairs += 1
        else:
            active_pairs += 1
            group_triggers[a[0], b[0]] += 1
    def active_count(way):
        return 0 if blocked[way] else counts[way]
    records = bytearray()
    states = exits = active_states = active_exits = 0
    for key in sorted(groups):
        from_way, via_way = key
        via_count = active_count(via_way)
        exit_bound = sum(active_count(to) for to in groups[key])
        states += via_count
        exits += exit_bound
        if group_triggers[key]:
            active_states += via_count
            active_exits += exit_bound
        records.extend(PREFIX_COUNT.pack(identities[from_way], identities[via_way], via_count,
                                         exit_bound, group_rules[key], group_triggers[key]))
    count = len(groups)
    field_bytes = 8*(count+1)+3*(states+exits)+9*active_pairs
    check()
    report = {'status': 'complete_typed_static_turn_context_footprint_inventory',
              'waysChecked': way_count, 'completePreArcsChecked': pre, 'retainedArcsCounted': retained,
              'closureIdsRetained': closure_count, 'rulesChecked': seen,
              'resolvedRulesRetained': statuses[0], 'inactiveMissingMemberRulesRetained': statuses[3],
              'noJoinFallbackRulesRetained': statuses[2], 'allResolvedPrefixGroups': count,
              'activeEntryPrefixGroups': len(group_triggers), 'sourcePreEntryPairsChecked': len(pairs),
              'activeEntryPairs': active_pairs, 'entryPairsBlockedByOtherClosures': dropped_pairs,
              'additionalContextStateUpperBound': states, 'possibleStatesIncludingOrdinaryArcs': post_count+states,
              'possibleExitArcRecordsUpperBound': exits,
              'activePrefixOnlyContextStates': active_states, 'activePrefixOnlyExitArcUpperBound': active_exits,
              'rawContextRuntimeFieldsUpperBoundBytes': field_bytes,
              'triggerIncomingBitsetBytes': (post_count+7)//8,
              'additionalQueryLabelBytes': 4*states,
              'denseCountryTypedColumnsBackingBytes': identities.buffer_info()[1]*identities.itemsize+counts.buffer_info()[1]*counts.itemsize+len(blocked),
              'boundedSelectedPreArcRecords': len(selected_arcs), 'prefixCountArtifactBytes': len(records),
              'hostOperationSecondsIncludingFactAndMetadataReads': time.monotonic()-began,
              'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'nativeKernelExecutions': 0,
              'routingQueries': 0, 'coordinatesRead': 0, 'nationalNodeDictionaryBuilt': False,
              'sourceCostsOrFlagsOrClosureUnionChanged': False, 'runtimeArtifactBuilt': False,
              'accuracyOrAppQualified': False,
              'scope': 'Complete metadata footprint only. All resolved prefixes counted, including prefixes blocked by other closures; every retained via arc and all retained prohibited-to-way arcs conservatively counted. Bounds are not an encoded runtime, exact exit-join count, query/memory/package/ETA or app admission. All rule statuses/source union retained; no post-closure absence inference or permission change.'}
    return report, bytes(records)
