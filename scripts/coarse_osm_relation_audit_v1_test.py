from array import array
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

from coarse_osm_relation_audit_v1 import fact_rows, RelationAudit


def relation(identity, via='way'):
    return {'type': 'relation', 'id': identity, 'tags': {'type': 'restriction', 'restriction': 'no_left_turn'},
            'members': [{'type': 'way', 'ref': 10, 'role': 'from'}, {'type': via, 'ref': 20, 'role': 'via'}, {'type': 'way', 'ref': 30, 'role': 'to'}]}


class Controls(unittest.TestCase):
    def test_exact_supported_unsupported_and_invalid_metadata(self):
        invalid = {'id': 3, 'tags': {'type': 'restriction', 'restriction': 'no_left_turn'}, 'members': [{'type': 'relation', 'ref': 100, 'role': ''}]}
        output = io.BytesIO()
        sink = RelationAudit([(1, 10, 20, 30, 0, b'\0'*7)], array('Q', [10, 20, 30]), [invalid], output,
                             expected_supported=1, expected_unsupported=1)
        for e in [relation(1, 'node'), relation(2), invalid]:
            sink.consume(e)
        r = sink.finish()
        self.assertEqual(r['closureWayIdsMatched'], 3)
        self.assertEqual(r['unlocatableSourceRecordsMatched'], 1)
        self.assertEqual(output.getvalue().count(b'\n'), 1)

    def test_supported_turn_drift_and_missing_tail_fail(self):
        sink = RelationAudit([], array('Q'), [], io.BytesIO(), expected_supported=0, expected_unsupported=0)
        with self.assertRaises(Exception):
            sink.consume(relation(1, 'node'))
        sink = RelationAudit([(1, 10, 20, 30, 0, b'\0'*7)], array('Q'), [], io.BytesIO(), expected_supported=1, expected_unsupported=0)
        with self.assertRaises(Exception):
            sink.finish()

    def test_closure_union_and_classification_counts_are_exact(self):
        for ids, count in [([10, 20], 1), ([10, 20, 30], 2)]:
            sink = RelationAudit([], array('Q', ids), [], io.BytesIO(), expected_supported=0, expected_unsupported=count)
            sink.consume(relation(1))
            with self.assertRaises(Exception):
                sink.finish()

    def test_unexpected_unlocatable_record_cannot_be_silently_dropped(self):
        sink = RelationAudit([], array('Q'), [], io.BytesIO(), expected_supported=0, expected_unsupported=0)
        e = relation(1)
        e['members'] = [{'type': 'relation', 'ref': 100, 'role': ''}]
        with self.assertRaises(Exception):
            sink.consume(e)

    def test_selected_output_cap_fails_before_writing_over_limit(self):
        out = io.BytesIO()
        sink = RelationAudit([], array('Q', [10, 20, 30]), [], out, expected_supported=0, expected_unsupported=1, max_output=1)
        with self.assertRaises(Exception):
            sink.consume(relation(1))
        self.assertEqual(out.getvalue(), b'')

    def test_fact_records_cross_chunks_without_dropping_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'cost-facts').mkdir()
            body = struct.pack('<QQ', 10, 20)
            roster = {}
            for i, raw in enumerate([body[:11], body[11:]]):
                name = f'cost-facts/closures-{i:04d}.bin'
                (root/name).write_bytes(raw)
                roster[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            self.assertEqual(list(fact_rows(root, roster, 'closures', struct.Struct('<Q'))), [(10,), (20,)])
            roster[name]['sha256'] = '0'*64
            with self.assertRaises(Exception):
                list(fact_rows(root, roster, 'closures', struct.Struct('<Q')))


if __name__ == '__main__':
    unittest.main()
