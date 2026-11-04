"""Independent complete split multiset audit, using sealed typed incidence streams."""
from array import array
import hashlib
import heapq
import json
from pathlib import Path
import struct
import tempfile
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REF = struct.Struct('<QQII')
WORD = struct.Struct('<Q')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(path, shape):
    assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 67108864
    assert path.stat().st_size % shape.size == 0
    with path.open('rb') as stream:
        while raw := stream.read(shape.size * 16384):
            assert len(raw) % shape.size == 0
            yield from shape.iter_unpack(raw)


def expected_splits(references, tags, relation_nodes, check=lambda: None):
    streams = []
    for path in references:
        def ordered(path=path):
            previous = None
            for row in rows(path, REF):
                node, way, degree, end = row
                key = node, way, end, degree
                assert 0 < node < 2**63 and 0 < way < 2**63 and end in (0, 1) and degree == (1 if end else 2)
                assert previous is None or previous <= key
                previous = key
                yield row
        streams.append(ordered())
    tag_rows = (value for path in tags for value, in rows(path, WORD))
    tag = next(tag_rows, None)
    tag_count = int(tag is not None)
    prior_tag = 0
    relation_cursor = 0
    expected = array('Q')
    counts = {'references': 0, 'totalDegree': 0, 'endpointOccurrences': 0, 'uniqueNodes': 0, 'anchors': 0,
              'taggedSelectedNodes': 0, 'relationNodeSelectedNodes': 0, 'degreeNotTwoNodes': 0, 'wayEndUniqueNodes': 0,
              'anchorsWithoutWayEndsBeforeCycleAndCarRules': 0}
    node = degree = 0
    endpoint = False
    internal = array('Q')
    def finish():
        nonlocal tag, tag_count, prior_tag, relation_cursor
        if not node:
            return
        while tag is not None and tag < node:
            assert tag > prior_tag
            prior_tag = tag
            tag = next(tag_rows, None)
            tag_count += tag is not None
        while relation_cursor < len(relation_nodes) and relation_nodes[relation_cursor] < node:
            relation_cursor += 1
        tagged = tag == node
        explicit = relation_cursor < len(relation_nodes) and relation_nodes[relation_cursor] == node
        junction = degree != 2
        anchor = endpoint or tagged or explicit or junction
        counts['uniqueNodes'] += 1
        counts['anchors'] += anchor
        counts['taggedSelectedNodes'] += tagged
        counts['relationNodeSelectedNodes'] += explicit
        counts['degreeNotTwoNodes'] += junction
        counts['wayEndUniqueNodes'] += endpoint
        counts['anchorsWithoutWayEndsBeforeCycleAndCarRules'] += tagged or explicit or junction
        if anchor:
            assert len(expected) + len(internal) <= 2447509
            expected.extend(internal)
    for value, way, d, end in heapq.merge(*streams, key=lambda r: (r[0], r[1], r[3], r[2])):
        if value != node:
            finish()
            node, degree, endpoint = value, 0, False
            internal = array('Q')
        counts['references'] += 1
        assert counts['references'] <= 48163649
        if counts['references'] % 262144 == 0:
            check()
        counts['totalDegree'] += d
        counts['endpointOccurrences'] += end
        degree += d
        endpoint |= bool(end)
        if not end:
            assert len(internal) < 1000000
            internal.append(way)
    finish()
    while tag is not None:
        assert tag > prior_tag
        prior_tag = tag
        tag = next(tag_rows, None)
        tag_count += tag is not None
    counts['allTaggedNodes'] = tag_count
    return counts, expected


def self_test():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        ref = root/'refs'
        tag = root/'tags'
        # Source way1=[1,2,3], way2=[3,4]; internal2 is retained only if tagged/referenced.
        records = [(1, 1, 1, 1), (2, 1, 2, 0), (3, 1, 1, 1), (3, 2, 1, 1), (4, 2, 1, 1)]
        ref.write_bytes(b''.join(REF.pack(*r) for r in records))
        counts, expected = expected_splits([ref], [], array('Q'))
        assert list(expected) == [] and counts['anchors'] == 3 and counts['uniqueNodes'] == 4
        tag.write_bytes(WORD.pack(2))
        counts, expected = expected_splits([ref], [tag], array('Q'))
        assert list(expected) == [1] and counts['anchors'] == 4 and counts['taggedSelectedNodes'] == 1
        counts, expected = expected_splits([ref], [], array('Q', [2, 2]))
        assert list(expected) == [1] and counts['relationNodeSelectedNodes'] == 1
        ref.write_bytes(b'x')
        try:
            expected_splits([ref], [], array('Q'))
            raise RuntimeError('Truncated reference accepted')
        except AssertionError:
            pass
    return {'checks': 4, 'successful': True}


def audit():
    began = time.monotonic()
    assert self_test()['successful']
    base = REPO/'data/coarse-quality/us-osm-topology-run-v1'
    derived = REPO/'data/coarse-quality/us-osm-car-capacity-derive-v2'
    topology = json.loads((base/'topology.json').read_bytes())
    result = json.loads((derived/'result.json').read_bytes())
    pins = topology['artifacts']
    references = [base/'streams'/name for name in sorted(pins) if name.startswith('refs-')]
    tags = [base/'streams'/name for name in sorted(pins) if name.startswith('tagged-')]
    metadata = base/'streams/sorted-relation-nodes-0000.bin'
    for path in [*references, *tags, metadata]:
        pin = pins[path.name]
        assert path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256']
    relation_nodes = array('Q')
    relation_nodes.frombytes(metadata.read_bytes())
    assert len(relation_nodes) == 1201443 and all(a <= b for a, b in zip(relation_nodes, relation_nodes[1:]))
    def check():
        assert time.monotonic() - began < 600
    counts, expected = expected_splits(references, tags, relation_nodes, check)
    actual = array('Q')
    actual.frombytes((derived/'splits.u64').read_bytes())
    assert len(actual) == len(expected) == 2447509 and list(actual) == sorted(expected)
    for name, value in counts.items():
        assert value == result[name], (name, value, result[name])
    assert counts['references'] == 48163649 and counts['anchors'] == 5731903 and counts['uniqueNodes'] == 42993567
    assert counts['totalDegree'] == 2*43936411 and counts['endpointOccurrences'] == 2*4227238
    assert 4227238 + len(expected) == result['contractedEdges'] == 6674747
    assert sha(derived/'splits.u64') == result['splitSha256'] and (derived/'splits.u64').stat().st_size == result['splitBytes'] == 19580072
    return {'status': 'independent_complete_native_partition_multiset_passed', 'auditorSha256': sha(Path(__file__)),
            'resultSha256': sha(derived/'result.json'), 'splitSha256': result['splitSha256'], 'sourceCounts': counts,
            'sourceFilesAuthenticated': len(references)+len(tags)+1, 'exactWaySplitOccurrencesChecked': len(expected),
            'selfTests': self_test(), 'secondsIncludingSourceHashesIndependentSelectionAndExactSortedComparison': time.monotonic()-began,
            'sourcePbfReads': 0, 'nativeLibraryExecutions': 0, 'networkRequests': 0, 'applicationDbReads': 0,
            'modelChanged': False, 'nationalGraphBuilt': False, 'etaQualified': False, 'vercelQualified': False}
