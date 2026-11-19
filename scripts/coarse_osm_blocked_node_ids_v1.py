"""Map every blocked graph vertex back to its exact original native node ID."""
import gzip
import hashlib
import json
from pathlib import Path
import struct


def map_nodes(graph_flags, permutation, anchors, identities, source_flags, check=lambda: None):
    count = len(graph_flags)
    assert len(permutation) == len(anchors) == len(source_flags) == count
    seen = bytearray((count+7)//8)
    output = []
    for vertex, old in enumerate(permutation):
        if vertex % 4096 == 0:
            check()
        assert type(old) is int and 0 <= old < count
        assert not seen[old >> 3] & (1 << (old & 7))
        seen[old >> 3] |= 1 << (old & 7)
        flag = graph_flags[vertex]
        assert 0 <= flag < 8 and source_flags[old] == flag
        if flag & 1:
            node = anchors[old]
            assert type(node) is int and 0 <= node < len(identities)
            identity = identities[node]
            assert type(identity) is int and 0 < identity < 2**64
            output.append({'vertex':vertex,'sourceAnchor':old,'sourceNodeIndex':node,
                           'sourceNodeId':str(identity),'flags':flag})
    assert len({row['sourceNodeId'] for row in output}) == len(output) <= 100000
    return output


def write_and_audit(graph_flags, permutation, anchors, identities, source_flags, root, check=lambda: None):
    root = Path(root)
    nodes = map_nodes(graph_flags, permutation, anchors, identities, source_flags, check)
    raw = json.dumps(nodes,separators=(',', ':')).encode()
    assert len(raw) <= 16777216
    packed = gzip.compress(raw,compresslevel=9,mtime=0)
    native = b''.join(struct.pack('<Q',value) for value in sorted(int(row['sourceNodeId']) for row in nodes))
    with (root/'blocked-nodes.json.gz').open('xb') as stream:
        stream.write(packed)
    with (root/'blocked-node-ids.u64').open('xb') as stream:
        stream.write(native)
    # Reopen both representations, reconstruct each tuple independently and
    # compare the complete blocked source selection, not just output counts.
    saved = json.loads(gzip.decompress((root/'blocked-nodes.json.gz').read_bytes()))
    selected = {i for i,flag in enumerate(graph_flags) if flag & 1}
    assert len(saved) == len(selected) and {row['vertex'] for row in saved} == selected
    for row in saved:
        assert set(row) == {'vertex','sourceAnchor','sourceNodeIndex','sourceNodeId','flags'}
        vertex = row['vertex'];old = permutation[vertex];source = anchors[old]
        assert (row['sourceAnchor'],row['sourceNodeIndex']) == (old,source)
        assert row['sourceNodeId'] == str(identities[source])
        assert row['flags'] == graph_flags[vertex] == source_flags[old]
    reopened = (root/'blocked-node-ids.u64').read_bytes()
    decoded = [row[0] for row in struct.iter_unpack('<Q',reopened)]
    assert decoded == sorted(int(row['sourceNodeId']) for row in saved)
    return {'blockedVertices':len(saved),'allVertexPermutationEntriesChecked':len(permutation),
            'allGraphToSourceFlagsCompared':len(graph_flags),
            'allNativeIdTuplesIndependentlyReplayed':len(saved),'nativeIdsRemainUint64':True,
            'artifacts':{
                'blocked-nodes.json.gz':{'bytes':len(packed),'sha256':hashlib.sha256(packed).hexdigest(),
                                         'rawBytes':len(raw),'rawSha256':hashlib.sha256(raw).hexdigest()},
                'blocked-node-ids.u64':{'bytes':len(native),'sha256':hashlib.sha256(native).hexdigest()}}}
