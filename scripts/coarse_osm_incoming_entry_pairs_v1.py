"""Merge source-certified bans whose incoming arc was absent from the old graph."""
from array import array
from pathlib import Path
import struct

from coarse_osm_car_packed_audit_v1 import ARC, rows, unpack24
from coarse_osm_entry_graph_audit_v1 import pairs
from coarse_timing_input import require

NONE = 0xffffffff


def merge_incoming_pairs(original, view, routing, old_pairs_path, combined_pairs_path, old_final_path,
                         output, dimensions, old_counts, check=lambda: None):
    original, view, routing = Path(original), Path(view), Path(routing)
    _, vertices, way_count, pre_count, post_count, _ = dimensions
    old_pairs = pairs(old_pairs_path, 4)
    combined = pairs(combined_pairs_path, 4)
    require(set(old_pairs) <= set(combined) and old_counts[0] == len(old_pairs), 'Every original native entry pair retained')
    additional = sorted(set(combined) - set(old_pairs))
    require(len(additional) <= 1048576 and all(0 <= a < pre_count and 0 <= b < pre_count for a,b in additional),
            'Bounded complete incoming-only pre-arc pairs')
    ways = array('Q', (row[0] for row in rows(original, 'ways', struct.Struct('<QddII'))))
    require(len(ways) == way_count, 'Complete original source way membership')
    old_closed = {row[0] for row in rows(original, 'closures', struct.Struct('<Q'))}
    closed = {row[0] for row in rows(view, 'closures', struct.Struct('<Q'))}
    require(closed <= old_closed, 'Only source-qualified closure removals')
    offsets = unpack24((routing/'offsets.u24').read_bytes())
    targets = unpack24((routing/'targets.u24').read_bytes())
    require(len(offsets) == vertices+1 and offsets[0] == 0 and offsets[-1] == len(targets) == post_count and
            all(a <= b for a,b in zip(offsets,offsets[1:])), 'Complete bounded ordered CSR')
    cursor = array('I', offsets[:-1])
    needed = {arc for pair in additional for arc in pair}
    selected = {}
    seen = retained = 0
    for index, (tail,head,way,*_) in enumerate(rows(original,'arcs',ARC)):
        require(index < pre_count and tail < vertices and head < vertices and way < way_count, 'Every source pre-arc domain')
        mapped = NONE
        if ways[way] not in closed:
            mapped = cursor[tail]
            require(mapped < offsets[tail+1] and targets[mapped] == head, 'Actual source-to-CSR row and endpoint correspondence')
            cursor[tail] += 1
            retained += 1
        if index in needed:
            selected[index] = (mapped,tail,head,ways[way] in old_closed)
        seen += 1
        if index % 65536 == 0: check()
    require(seen == pre_count and retained == post_count and cursor == array('I',offsets[1:]) and set(selected) == needed,
            'Every source arc/CSR row/selected pair endpoint replayed')
    added = set()
    active = dropped = 0
    for a,b in additional:
        incoming,outgoing = selected[a],selected[b]
        require(incoming[3], 'Incoming arc must have been absent from the original graph')
        require(incoming[2] == outgoing[1], 'Every incoming-only source pair joins at one node')
        if incoming[0] == NONE or outgoing[0] == NONE:
            dropped += 1
        else:
            added.add((incoming[0],outgoing[0]));active += 1
    old_final = pairs(old_final_path,3)
    require(len(old_final) == old_counts[4] and old_counts[5] == post_count, 'Complete unchanged native final-pair baseline')
    final = sorted(set(old_final) | added)
    require(len(final)*6 <= 6291456, 'Complete final turn-pair budget')
    raw = b''.join(a.to_bytes(3,'little')+b.to_bytes(3,'little') for a,b in final)
    with Path(output).open('xb') as stream: stream.write(raw)
    require(pairs(output,3) == final, 'Every final entry-pair byte reopens exactly')
    counts = [len(combined),old_counts[1],old_counts[2]+active,old_counts[3]+dropped,len(final),post_count]
    return counts, {'allSourcePreArcsReplayed':seen,'newIncomingOnlySourcePairs':len(additional),
                    'newActivePairs':active,'newDroppedPairs':dropped,'allOriginalNativeFinalPairsRetained':True,
                    'allNewIncomingArcsOriginallyClosed':True,'noOldAllowedTransitionRemoved':True}
