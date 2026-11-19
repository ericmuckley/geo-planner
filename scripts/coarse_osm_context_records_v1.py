"""Construct compact source-native turn-context records, without routing."""
from array import array
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, rows, unpack24
from coarse_osm_context_footprint_v1 import PREFIX_COUNT, inventory
from coarse_osm_entry_graph_audit_v1 import pairs
from coarse_osm_entry_resolution_audit_v1 import fixed

CONTEXT_FIELDS = ('state-offsets.u32', 'state-arcs.u24', 'exit-offsets.u32',
                  'exit-arcs.u24', 'triggers.u24', 'trigger-incoming.bit')


def u24(values):
    return b''.join(n.to_bytes(3, 'little') for n in values)


def u32(values):
    return b''.join(struct.pack('<I', n) for n in values)


def build(source, rule_path, decision_path, pair_path, offsets_path, targets_path,
          permutation_path, source_turn_path, final_spatial_turn_path, dimensions, check=lambda: None):
    began = time.monotonic()
    footprint, prefix_counts = inventory(source, rule_path, decision_path, pair_path, dimensions, check)
    way_count, vertices, pre_count, post_count, _ = dimensions
    identities = array('Q', (r[0] for r in rows(source, 'ways', struct.Struct('<Q24x'))))
    assert len(identities) == way_count
    closed = {r[0] for r in rows(source, 'closures', struct.Struct('<Q'))}
    blocked = bytearray(identity in closed for identity in identities)
    groups = defaultdict(set)
    for rule, decision in zip(fixed(rule_path, struct.Struct('<QQQQ'), 100000), fixed(decision_path, struct.Struct('<QII'), 100000), strict=True):
        if decision[1] == 0:
            groups[rule[1:3]].add(rule[3])
    keys = sorted(groups)
    group_index = {key: i for i, key in enumerate(keys)}
    bounds = list(PREFIX_COUNT.iter_unpack(prefix_counts))
    assert [row[:2] for row in bounds] == keys
    selected_way_ids = {via for _, via in keys} | {to for values in groups.values() for to in values}
    selected_way_indices = {bisect_left(identities, identity) for identity in selected_way_ids}
    assert all(at < way_count and identities[at] in selected_way_ids for at in selected_way_indices)
    offsets = unpack24(Path(offsets_path).read_bytes())
    targets = unpack24(Path(targets_path).read_bytes())
    permutation = array('I')
    permutation.frombytes(Path(permutation_path).read_bytes())
    assert len(offsets) == vertices+1 and offsets[0] == 0 and offsets[-1] == post_count
    assert all(a <= b for a, b in zip(offsets, offsets[1:]))
    assert len(targets) == len(permutation) == post_count
    seen = bytearray((post_count+7)//8)
    for arc in permutation:
        assert arc < post_count and not seen[arc >> 3] & (1 << (arc & 7))
        seen[arc >> 3] |= 1 << (arc & 7)
    del seen
    entry_pairs = list(fixed(pair_path, struct.Struct('<II'), 200000))
    selected_pre = {n for pair in entry_pairs for n in pair}
    entry_arcs, by_way = {}, defaultdict(list)
    cursors = array('I', offsets[:-1])
    selected_count = retained = pre = 0
    selected_cap = footprint['additionalContextStateUpperBound']+footprint['possibleExitArcRecordsUpperBound']
    for tail, head, way, *_ in rows(source, 'arcs', ARC):
        assert pre < pre_count and tail < vertices and head < vertices and way < way_count
        arc = None
        if not blocked[way]:
            old_arc = cursors[tail]
            assert old_arc < offsets[tail+1] and targets[old_arc] == head
            cursors[tail] += 1
            arc = permutation[old_arc]
            retained += 1
            if way in selected_way_indices:
                by_way[identities[way]].append((arc, tail, head, pre))
                selected_count += 1
                assert selected_count <= selected_cap
        if pre in selected_pre:
            entry_arcs[pre] = arc, identities[way], tail, head
        pre += 1
        if pre % 65536 == 0:
            check()
    assert pre == pre_count and retained == post_count and cursors == array('I', offsets[1:])
    assert set(entry_arcs) == selected_pre
    state_offsets, state_arcs, exit_offsets, exit_arcs = [0], [], [0], []
    for group, key in enumerate(keys):
        via = by_way[key[1]]
        states = sorted(row[0] for row in via)
        assert len(states) == bounds[group][2] and len(set(states)) == len(states)
        heads = {row[2] for row in via}
        exits = sorted({row[0] for to in groups[key] for row in by_way[to] if row[1] in heads})
        assert len(exits) <= bounds[group][3] and not set(states) & set(exits)
        state_arcs.extend(states)
        state_offsets.append(len(state_arcs))
        exit_arcs.extend(exits)
        exit_offsets.append(len(exit_arcs))
    assert len(state_arcs) == footprint['additionalContextStateUpperBound']
    triggers = []
    for incoming, following in entry_pairs:
        a, b = entry_arcs[incoming], entry_arcs[following]
        assert a[3] == b[2] and (a[1], b[1]) in group_index
        if a[0] is None or b[0] is None:
            continue
        group = group_index[a[1], b[1]]
        state = bisect_left(state_arcs, b[0], state_offsets[group], state_offsets[group+1])
        assert state < state_offsets[group+1] and state_arcs[state] == b[0]
        triggers.append((a[0], b[0], state))
    triggers.sort()
    assert len(triggers) == footprint['activeEntryPairs'] and len({row[:2] for row in triggers}) == len(triggers)
    source_pairs = pairs(source_turn_path, 3)
    supported = sorted((permutation[a], permutation[b]) for a, b in source_pairs)
    assert len(set(supported)) == len(supported)
    actual = pairs(final_spatial_turn_path, 3)
    assert sorted(set(supported) | {row[:2] for row in triggers}) == actual
    incoming_bits = bytearray((post_count+7)//8)
    for before, _, _ in triggers:
        incoming_bits[before >> 3] |= 1 << (before & 7)
    fields = dict(zip(('context/'+name for name in CONTEXT_FIELDS),
                      (u32(state_offsets), u24(state_arcs), u32(exit_offsets), u24(exit_arcs),
                       u24(n for row in triggers for n in row), bytes(incoming_bits)), strict=True))
    fields['routing/forbidden-turns.u24'] = u24(n for row in supported for n in row)
    fields['prefix-counts.bin'] = prefix_counts
    context_bytes = sum(len(fields['context/'+name]) for name in CONTEXT_FIELDS)
    assert context_bytes <= footprint['rawContextRuntimeFieldsUpperBoundBytes']+footprint['triggerIncomingBitsetBytes']
    check()
    return {'status': 'complete_context_records_independent_audit_pending',
            'waysChecked': way_count, 'completePreArcsMapped': pre, 'retainedArcsMapped': retained,
            'contextPrefixGroups': len(keys), 'contextStates': len(state_arcs), 'prohibitedExitArcRecords': len(exit_arcs),
            'activeTriggerPairs': len(triggers), 'supportedTurnPairsRetained': len(supported),
            'oldFinalForbiddenUnionPairsChecked': len(actual), 'oldAllowedPathsRemainOrdinary': True,
            'contextRuntimeBackingBytes': context_bytes, 'sourceOnlyForbiddenBytes': len(fields['routing/forbidden-turns.u24']),
            'offlinePrefixCountBytes': len(prefix_counts), 'selectedRetainedWayArcRecords': selected_count,
            'additionalQueryLabelBytes': 4*len(state_arcs), 'constructionSeconds': time.monotonic()-began,
            'sourcePbfReads': 0, 'sourceConstructorExecutions': 0, 'coordinatesRead': 0, 'routingQueries': 0,
            'sourceCostsFlagsClosureUnionOrPhysicalArcIdsChanged': False, 'appActivated': False,
            'scope': 'Compact context/source-only-turn records only. Every physical source arc/cost/flag/closure unchanged; all states/exits use source way/native shared-anchor identity, never coordinates. Source-only forbidden union context-trigger pairs is exactly the old final turn set, so every old allowed path keeps ordinary history. Independent full source audit/reader/search/paid-progress/lifetime/ETA/app gates remain.'}, fields
