"""Rebase a qualified flag-only correction from spatial vertices to native anchors."""
from array import array
from coarse_timing_input import require


def rebase_flags(native_before, spatial_before, spatial_after, spatial_to_native, ids, anchors, opened_node_ids):
    count = len(native_before)
    require(count > 0 and all(isinstance(value, bytes) and len(value) == count for value in
                            [native_before, spatial_before, spatial_after]), 'Complete flag profiles')
    require(len(spatial_to_native) == len(anchors) == count and
            all(value < 8 for raw in [native_before, spatial_before, spatial_after] for value in raw), 'Complete source flag dimensions/bits')
    require(opened_node_ids == sorted(set(opened_node_ids)) and all(type(i) is int and i > 0 for i in opened_node_ids),
            'Canonical source-qualified opened node identities')
    inverse = array('I', [0xffffffff]) * count
    result = bytearray(count)
    changed = []
    for vertex, anchor in enumerate(spatial_to_native):
        require(type(anchor) is int and 0 <= anchor < count and inverse[anchor] == 0xffffffff, 'Exact spatial-to-native bijection')
        inverse[anchor] = vertex
        before, after = spatial_before[vertex], spatial_after[vertex]
        require(before == native_before[anchor], 'Every old spatial flag exactly equals its native source anchor')
        require(before == after or (before & 1 and after == before & ~1), 'Only previously qualified blocker bits may clear')
        result[anchor] = after
        if before != after:
            source_index = anchors[anchor]
            require(type(source_index) is int and 0 <= source_index < len(ids), 'Changed native anchor binds to original source IDs')
            changed.append(ids[source_index])
    require(sorted(changed) == opened_node_ids, 'Every and only source-qualified opened node identity preserved')
    # A second pass in the opposite order checks both the inversion and every emitted byte.
    for anchor, vertex in enumerate(inverse):
        require(spatial_to_native[vertex] == anchor and result[anchor] == spatial_after[vertex] and
                native_before[anchor] == spatial_before[vertex], 'Independent every-anchor round-trip replay')
    return bytes(result), {'spatialAndNativeRowsIndependentlyCompared': count, 'sourceQualifiedOpenedNodeIdsPreserved': len(changed),
                           'everyOriginalFlagReproducedThroughBijection': True, 'everyFinalFlagRoundTripsExactly': True,
                           'signalsReversalAndIndependentBlockersPreserved': True,
                           'scope': 'Permutation only; no source access, node policy, physical membership or query change.'}
