"""Full independent base-field audit plus exact entry-pair union/superset proof.

Uses the sealed independent supported-turn auditor and a separately implemented
source-to-CSR map. Executes no native library, producer or routing query.
"""
from array import array
from bisect import bisect_right
from pathlib import Path
import struct
import time

from coarse_osm_car_packed_audit_v1 import ARC, audit as audit_base, rows, unpack24

NONE = 0xffffffff


def pairs(path, width):
    raw = Path(path).read_bytes()
    assert len(raw) <= 6291456 and len(raw) % (2*width) == 0
    if width == 3:
        words = unpack24(raw)
        result = list(zip(words[::2], words[1::2]))
    else:
        assert width == 4
        result = list(struct.iter_unpack('<II', raw))
    assert all(a < b for a, b in zip(result, result[1:]))
    return result


def audit(original, view, routing, extra_path, final_path, dimensions, native_counts, *, baseline_post, check=lambda: None):
    began = time.monotonic()
    original, view, routing = Path(original), Path(view), Path(routing)
    nodes, vertices, way_count, pre_count, count, turn_count = dimensions
    base = audit_base(view, routing, dimensions)
    check()
    ways = array('Q', (r[0] for r in rows(original, 'ways', struct.Struct('<QddII'))))
    assert len(ways) == way_count
    old = {n for n, in rows(original, 'closures', struct.Struct('<Q'))}
    closed = {n for n, in rows(view, 'closures', struct.Struct('<Q'))}
    assert closed <= old
    old_flags = bytearray(n in old for n in ways)
    new_flags = bytearray(n in closed for n in ways)
    offsets = unpack24((routing/'offsets.u24').read_bytes())
    targets = unpack24((routing/'targets.u24').read_bytes())
    assert len(offsets) == vertices+1 and len(targets) == count
    cursor = array('I', offsets[:-1])
    mapping = array('I', [NONE])*pre_count
    originally_closed = bytearray(pre_count)
    seen = retained = old_retained = 0
    for i, (tail, head, way, *_rest) in enumerate(rows(original, 'arcs', ARC)):
        assert i < pre_count and tail < vertices and head < vertices and way < way_count
        seen += 1
        originally_closed[i] = old_flags[way]
        old_retained += not old_flags[way]
        if new_flags[way]:
            continue
        arc = cursor[tail]
        assert arc < offsets[tail+1] and targets[arc] == head
        mapping[i] = arc
        cursor[tail] += 1
        retained += 1
        if i % 65536 == 0:
            check()
    assert seen == pre_count and retained == count and old_retained == baseline_post
    assert cursor == array('I', offsets[1:])
    base_pairs = pairs(routing/'forbidden-turns.u24', 3)
    source_pairs = pairs(extra_path, 4)
    active, dropped, additions = 0, 0, set()
    for a, b in source_pairs:
        assert a < pre_count and b < pre_count and originally_closed[a] and originally_closed[b]
        incoming, outgoing = mapping[a], mapping[b]
        if NONE in (incoming, outgoing):
            dropped += 1
            continue
        # Rank/source IDs and source order determine this map, never coordinates.
        assert targets[incoming] == bisect_right(offsets, outgoing)-1
        additions.add((incoming, outgoing))
        active += 1
    expected = sorted(set(base_pairs) | additions)
    actual = pairs(final_path, 3)
    assert actual == expected
    counts = [len(source_pairs), len(base_pairs), active, dropped, len(expected), retained]
    assert counts == native_counts
    check()
    return {'status': 'independent_complete_entry_graph_audit_passed', 'baseFields': base,
            'allPreArcMappingsChecked': seen, 'oldDirectedArcsRetained': old_retained,
            'reopenedDirectedArcs': retained-old_retained, 'augmentationCounts': counts,
            'finalForbiddenPairsChecked': len(actual), 'closureSubsetExact': True,
            'newEntryPairsOnlyTouchOriginallyClosedArcs': True,
            'oldAllowedTransitionsPreserved': True,
            'supersetReason': 'Every original open source arc retains cost/flags/reverse and supported-turn semantics; every added entry prohibition touches two originally closed arcs. The final turn set is exactly the supported set union mapped entries.',
            'secondsIndependentAuditIncludingAllBaseFields': time.monotonic()-began,
            'nativeLibraryExecutions': 0, 'sourcePbfReads': 0, 'routingQueries': 0,
            'accuracyOrAppQualified': False}
