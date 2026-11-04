import datetime
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from coarse_osm_relation_tail_v1 import selected_relations

STATE = '2026-10-25T21:21:21Z'
STAMP = int(datetime.datetime.fromisoformat(STATE.replace('Z', '+00:00')).timestamp())


def integer(n):
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(out)+bytes([n])


def number(key, value):
    return integer(key << 3)+integer(value)


def text(key, value):
    return integer((key << 3) | 2)+integer(len(value))+value


def packed(key, values):
    return text(key, b''.join(integer(v) for v in values))


def blob(kind, raw, compressed=True):
    body = number(2, len(raw))+text(3, zlib.compress(raw)) if compressed else text(1, raw)
    header = text(1, kind.encode())+number(3, len(body))
    return struct.pack('!I', len(header))+header+body


def source(rows, *, features=('OsmSchema-V0.6', 'DenseNodes'), state=STAMP, separate=False):
    strings = ['']
    def string(s):
        if s not in strings:
            strings.append(s)
        return strings.index(s)
    encoded = []
    for row in rows:
        tags = row.get('tags', {'type': 'restriction', 'restriction': 'no_u_turn'})
        members = row.get('members', [('way', 11, 'from'), ('way', 22, 'via'), ('way', 33, 'to')])
        meta = number(1, row.get('version', 3))+number(2, row.get('stamp', STAMP))+number(6, row.get('visible', 1))
        raw = number(1, row['id'])+packed(2, [string(k) for k in tags])+packed(3, [string(v) for v in tags.values()])+text(4, meta)
        previous, refs = 0, []
        for _, identity, _ in members:
            delta = identity-previous
            refs.append((delta << 1) ^ (delta >> 63))
            previous = identity
        raw += packed(8, [string(m[2]) for m in members])+packed(9, refs)+packed(10, [{'node': 0, 'way': 1, 'relation': 2, 'invalid': 3}[m[0]] for m in members])
        encoded.append(raw)
    table = text(1, b''.join(text(1, s.encode()) for s in strings))
    groups = [[r] for r in encoded] if separate else [encoded]
    header = b''.join(text(4, f.encode()) for f in features)+number(32, state)
    return blob('OSMHeader', header, False)+b''.join(blob('OSMData', table+text(2, b''.join(text(4, r) for r in group))+number(18, 1000)) for group in groups)


class Controls(unittest.TestCase):
    def scan(self, raw, count, **options):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'source.pbf'
            path.write_bytes(raw)
            rows = []
            stats = selected_relations(path, source_bytes=len(raw), state=STATE, expected_relations=count, consume=rows.append, **options)
            return rows, stats

    def test_complete_metadata_unicode_member_order_and_negative_deltas(self):
        members = [('way', 99, 'from'), ('way', 22, 'via'), ('way', 99, 'to')]
        tags = {'type': 'restriction', 'restriction:motorcar': 'no_u_turn', 'name': 'café 雪'}
        rows, stats = self.scan(source([{'id': 1, 'tags': tags, 'members': members}]), 1)
        self.assertEqual(rows, [{'type': 'relation', 'id': 1, 'version': 3, 'timestamp': STATE, 'visible': True, 'tags': tags,
                                  'members': [{'type': t, 'ref': i, 'role': r} for t, i, r in members]}])
        self.assertEqual(stats['relations'], 1)
        self.assertFalse(stats['earlierNodeWayBodiesValidated'])

    def test_count_all_relations_but_project_only_restriction_records(self):
        rows, stats = self.scan(source([{'id': 1, 'tags': {'type': 'route'}}, {'id': 2}]), 2)
        self.assertEqual([r['id'] for r in rows], [2])
        self.assertEqual(stats['restrictionRecordsSelected'], 1)
        self.assertEqual(stats['nodeWayObjectsProjected'], 0)

    def test_truncated_prefix_header_payload_and_corrupt_compression_fail(self):
        raw = source([{'id': 1}])
        for bad in [raw[:2], raw[:-1], raw[:-10]+b'X'*10]:
            with self.subTest(size=len(bad)), self.assertRaises(Exception):
                self.scan(bad, 1)

    def test_snapshot_features_and_duplicate_headers_fail(self):
        for raw in [source([{'id': 1}], state=STAMP-1), source([{'id': 1}], features=('OsmSchema-V0.6', 'HistoricalInformation'))]:
            with self.assertRaises(Exception):
                self.scan(raw, 1)
        raw = source([{'id': 1}])
        with self.assertRaises(Exception):
            self.scan(raw+raw, 2)

    def test_duplicate_out_of_order_zero_ids_and_count_mismatch_fail(self):
        for ids, count in [([1, 1], 2), ([2, 1], 2), ([0], 1), ([1], 2), ([1, 2], 1)]:
            with self.subTest(ids=ids, count=count), self.assertRaises(Exception):
                self.scan(source([{'id': i} for i in ids]), count)

    def test_member_types_id_domain_and_selected_metadata_fail(self):
        edits = [{'members': [('invalid', 1, 'from')]}, {'members': [('way', 0, 'from')]},
                 {'version': 0}, {'visible': 0}, {'stamp': STAMP+1}]
        for edit in edits:
            with self.subTest(edit=edit), self.assertRaises(Exception):
                self.scan(source([{'id': 1, **edit}]), 1)

    def test_tail_must_include_every_relation_not_only_a_valid_suffix(self):
        raw = source([{'id': 1}, {'id': 2}], separate=True)
        with self.assertRaises(Exception):
            self.scan(raw, 2, tail_bytes=1)

    def test_framing_compressed_decoded_and_tail_caps_fail(self):
        raw = source([{'id': 1}])
        for caps in [{'frame_cap': 1}, {'compressed_cap': 1}, {'decoded_cap': 1}, {'tail_bytes': 257*1048576}]:
            with self.subTest(caps=caps), self.assertRaises(Exception):
                self.scan(raw, 1, **caps)

    def test_input_size_and_symlink_guards(self):
        raw = source([{'id': 1}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'source.pbf'
            path.write_bytes(raw)
            link = Path(tmp)/'link.pbf'
            link.symlink_to(path)
            for candidate, size in [(path, len(raw)+1), (link, len(raw))]:
                with self.assertRaises(Exception):
                    selected_relations(candidate, source_bytes=size, state=STATE, expected_relations=1, consume=lambda _: None)

    def test_cancellation_propagates_without_claiming_complete_output(self):
        raw = source([{'id': 1}])
        def cancel():
            raise TimeoutError('test cancellation')
        with self.assertRaises(TimeoutError):
            self.scan(raw, 1, check=cancel)


if __name__ == '__main__':
    unittest.main()
