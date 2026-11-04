from array import array
import hashlib
import io
import json
import struct
import unittest

from coarse_osm_entry_records_v1 import ENTRY, prepare


def relation(identity, kind='no_u_turn', a=10, b=20, c=30):
    return {'type': 'relation', 'id': identity, 'tags': {'type': 'restriction', 'restriction': kind},
            'members': [{'type': 'way', 'role': role, 'ref': value} for role, value in [('from', a), ('via', b), ('to', c)]]}


class Controls(unittest.TestCase):
    def call(self, rows, expected_closures, **changes):
        raw = b''.join((json.dumps(r)+'\n').encode() for r in rows)
        expected = {'expected_rows': len(rows), 'expected_bytes': len(raw), 'expected_sha256': hashlib.sha256(raw).hexdigest(), 'expected_closures': array('Q', expected_closures)}
        expected.update(changes)
        a, b = io.BytesIO(), io.BytesIO()
        report = prepare(io.BytesIO(raw), a, b, **expected)
        return report, a.getvalue(), b.getvalue()

    def test_exact_typed_little_endian_rule_and_fallback(self):
        report, a, b = self.call([relation(1), relation(2, 'only_straight_on', 20, 30, 40)], [10, 20, 30, 40])
        self.assertEqual(a, ENTRY.pack(1, 10, 20, 30))
        self.assertEqual(list(struct.iter_unpack('<Q', b)), [(20,), (30,), (40,)])
        self.assertEqual((report['candidateRules'], report['fallbackRelations']), (1, 1))

    def test_conditionals_multiple_via_and_missing_roles_keep_source_closures(self):
        edits = [lambda e: e['tags'].update({'restriction:conditional': 'no_u_turn @ (Mo-Fr)'}),
                 lambda e: e['members'].append({'type': 'way', 'role': 'via', 'ref': 40}),
                 lambda e: e['members'][1].update({'role': 'unknown'})]
        for edit in edits:
            e = relation(1)
            edit(e)
            ids = sorted({m['ref'] for m in e['members']})
            report, a, b = self.call([e], ids)
            self.assertEqual(report['candidateRules'], 0)
            self.assertEqual(a, b'')
            self.assertEqual([v[0] for v in struct.iter_unpack('<Q', b)], ids)

    def test_high_native_ids_and_same_from_to_are_preserved(self):
        value = 2**40
        _, a, _ = self.call([relation(value, a=value+1, b=value+2, c=value+1)], [value+1, value+2])
        self.assertEqual(ENTRY.unpack(a), (value, value+1, value+2, value+1))

    def test_closure_union_drift_fails(self):
        with self.assertRaises(Exception):
            self.call([relation(1)], [10, 20])

    def test_sha_count_and_byte_changes_fail(self):
        for change in [{'expected_sha256': '0'*64}, {'expected_rows': 2}, {'expected_bytes': 1}]:
            with self.subTest(change=change), self.assertRaises(Exception):
                self.call([relation(1)], [10, 20, 30], **change)

    def test_duplicate_ids_or_nonunsupported_source_cannot_be_dropped(self):
        for rows in [[relation(1), relation(1)], [relation(2), relation(1)]]:
            with self.assertRaises(Exception):
                self.call(rows, [10, 20, 30])
        e = relation(1)
        e['members'][1]['type'] = 'node'
        with self.assertRaises(Exception):
            self.call([e], [10, 30])

    def test_declared_input_and_closure_caps_fail(self):
        for change in [{'expected_rows': 100001}, {'expected_bytes': 67108865}, {'expected_closures': array('Q', [20, 10])}]:
            with self.assertRaises(Exception):
                self.call([relation(1)], [10, 20, 30], **change)


if __name__ == '__main__':
    unittest.main()
