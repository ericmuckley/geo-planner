"""Independently verify every compact context record against complete source facts."""
from array import array
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, rows, unpack24
from coarse_osm_context_footprint_v1 import PREFIX_COUNT, inventory
from coarse_osm_context_records_v1 import CONTEXT_FIELDS
from coarse_osm_entry_attributes_v1 import annotate
from coarse_osm_entry_graph_audit_v1 import pairs
from coarse_osm_entry_resolution_audit_v1 import fixed


def audit(source, rule_path, decision_path, pair_path, offsets_path, permutation_path,
          source_turn_path, final_spatial_turn_path, output, dimensions, check=lambda: None):
    began = time.monotonic()
    footprint, prefix_raw = inventory(source, rule_path, decision_path, pair_path, dimensions, check)
    output = Path(output)
    assert (output/'prefix-counts.bin').read_bytes() == prefix_raw
    assert {p.name for p in (output/'context').iterdir()} == set(CONTEXT_FIELDS)
    def read(name):
        path = output/name
        assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 67108864
        return path.read_bytes()
    def offsets(name):
        raw = read('context/'+name)
        assert len(raw) % 4 == 0
        result = [r[0] for r in struct.iter_unpack('<I', raw)]
        assert result and result[0] == 0 and all(a <= b for a, b in zip(result, result[1:]))
        return result
    state_offsets, exit_offsets = offsets('state-offsets.u32'), offsets('exit-offsets.u32')
    states = unpack24(read('context/state-arcs.u24'))
    exits = unpack24(read('context/exit-arcs.u24'))
    raw_triggers = unpack24(read('context/triggers.u24'))
    assert len(raw_triggers) % 3 == 0
    triggers = list(zip(raw_triggers[::3], raw_triggers[1::3], raw_triggers[2::3], strict=True))
    prefix = list(PREFIX_COUNT.iter_unpack(prefix_raw))
    assert len(state_offsets) == len(exit_offsets) == len(prefix)+1
    assert state_offsets[-1] == len(states) == footprint['additionalContextStateUpperBound']
    assert exit_offsets[-1] == len(exits) <= footprint['possibleExitArcRecordsUpperBound']
    assert len(triggers) == footprint['activeEntryPairs'] and all(a < b for a, b in zip(triggers, triggers[1:]))
    assert len({r[:2] for r in triggers}) == len(triggers)
    _, _, pre_count, post_count, _ = dimensions
    selected = set(states) | set(exits) | {n for before, after, _ in triggers for n in (before, after)}
    assert all(arc < post_count for arc in selected) and len(selected) <= 200000
    attributes = annotate(source, offsets_path, permutation_path, selected, dimensions[:4], check)
    entry_pairs = list(fixed(pair_path, struct.Struct('<II'), 200000))
    selected_pre = {r['sourcePreArc'] for r in attributes.values()} | {n for pair in entry_pairs for n in pair}
    to_ways = defaultdict(set)
    for rule, decision in zip(fixed(rule_path, struct.Struct('<QQQQ'), 100000), fixed(decision_path, struct.Struct('<QII'), 100000), strict=True):
        assert rule[0] == decision[0]
        if decision[1] == 0:
            to_ways[rule[1:3]].add(rule[3])
    keys = [row[:2] for row in prefix]
    assert keys == sorted(to_ways)
    identities = array('Q', (row[0] for row in rows(source, 'ways', struct.Struct('<Q24x'))))
    closed = {row[0] for row in rows(source, 'closures', struct.Struct('<Q'))}
    wanted_to = {way for values in to_ways.values() for way in values}
    source_records, to_arcs = {}, defaultdict(list)
    seen = to_count = 0
    for tail, head, way, *_ in rows(source, 'arcs', ARC):
        identity = identities[way]
        if seen in selected_pre:
            source_records[seen] = identity, tail, head, identity in closed
        if identity in wanted_to and identity not in closed:
            to_arcs[identity].append((seen, tail))
            to_count += 1
            assert to_count <= footprint['possibleExitArcRecordsUpperBound']
        seen += 1
        if seen % 65536 == 0:
            check()
    assert seen == pre_count and set(source_records) == selected_pre
    for group, key in enumerate(keys):
        members = list(states[state_offsets[group]:state_offsets[group+1]])
        assert len(members) == prefix[group][2] and all(a < b for a, b in zip(members, members[1:]))
        assert all(attributes[a]['sourceWay'] == key[1] for a in members)
        heads = {source_records[attributes[a]['sourcePreArc']][2] for a in members}
        expected_exits = {pre for way in to_ways[key] for pre, tail in to_arcs[way] if tail in heads}
        actual = list(exits[exit_offsets[group]:exit_offsets[group+1]])
        assert all(a < b for a, b in zip(actual, actual[1:]))
        assert {attributes[a]['sourcePreArc'] for a in actual} == expected_exits
    actual_pairs = set()
    bits = bytearray((post_count+7)//8)
    for incoming, following, state in triggers:
        assert state < len(states) and states[state] == following
        group = bisect_right(state_offsets, state)-1
        assert group < len(keys)
        a, b = attributes[incoming], attributes[following]
        assert (a['sourceWay'], b['sourceWay']) == keys[group]
        before, after = a['sourcePreArc'], b['sourcePreArc']
        assert source_records[before][2] == source_records[after][1]
        actual_pairs.add((before, after))
        bits[incoming >> 3] |= 1 << (incoming & 7)
    expected_pairs = {(a, b) for a, b in entry_pairs if not source_records[a][3] and not source_records[b][3]}
    assert actual_pairs == expected_pairs and read('context/trigger-incoming.bit') == bytes(bits)
    permutation = array('I')
    permutation.frombytes(Path(permutation_path).read_bytes())
    expected_source = sorted((permutation[a], permutation[b]) for a, b in pairs(source_turn_path, 3))
    source_only = pairs(output/'routing/forbidden-turns.u24', 3)
    assert source_only == expected_source
    assert sorted(set(source_only) | {row[:2] for row in triggers}) == pairs(final_spatial_turn_path, 3)
    check()
    return {'status': 'independent_complete_context_state_exit_trigger_source_audit_passed',
            'allContextPrefixesChecked': len(keys), 'allContextStatesSourceMapped': len(states),
            'allProhibitedExitArcRecordsChecked': len(exits), 'allActiveEntryTriggerPairsChecked': len(triggers),
            'completePreArcsChecked': seen, 'selectedSourceArcAttributesChecked': len(attributes),
            'allSupportedTurnPairsRetained': len(source_only), 'oldFinalTurnUnionExact': True,
            'allOldAllowedPathsRemainOrdinary': True, 'sourcePbfReads': 0, 'sourceConstructorExecutions': 0,
            'coordinatesRead': 0, 'routingQueries': 0, 'appActivated': False,
            'secondsIndependentSourceAudit': time.monotonic()-began,
            'scope': 'Every via-state subset has complete retained-way cardinality and exact source-way identity. Every exit is independently enumerated from complete to-way source arcs/shared native anchors; every trigger maps to its proper context and source pre-entry pair. Source-only forbidden union triggers equals old final turn set. No runtime query/paid-progress/lifetime/ETA/full-app admission.'}
