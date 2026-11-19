import gzip
import json
from pathlib import Path
import tempfile
import unittest

from coarse_osm_source_gap_geometry_v1 import audit, capture


class SourceGapGeometryTests(unittest.TestCase):
    def run_capture(self, ways, refs, xy, closed=frozenset()):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'geometries.jsonl.gz'
            report = capture(ways, refs, xy, set(closed), path)
            records = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
            return report, records

    def test_all_negative_and_final_closed_positive_rows_selected_with_overlap_and_unknowns(self):
        ways = [(10, 50., 50., 3, 2), (20, 0., 0., 6 << 8, 4), (30, 50., 0., 1, 6)]
        report, rows = self.run_capture(ways, [0, 1, 1, 2, 2, 3], [0, 0, 1, 0, 2, 0, 3, 0], {20, 30, 999})
        self.assertEqual([row['sourceWay'] for row in rows], [20, 30])
        self.assertEqual(report['baseIneligibleMajorWays'], 1)
        self.assertEqual(report['baseEligibleFinalClosedMajorWays'], 1)
        self.assertEqual(report['finalClosureIdsOutsideMajorWayTable'], 1)
        self.assertEqual(report['selectedSourceReferences'], 4)

    def test_duplicate_and_empty_source_geometry_and_original_flags_are_preserved(self):
        ways = [(10, 0., 0., 5 << 8, 3), (20, 0., 0., 8 << 8, 3)]
        report, rows = self.run_capture(ways, [0, 0, 1], [10, 20, 30, 40])
        self.assertEqual(rows[0]['xyE7'], [[10, 20], [10, 20], [30, 40]])
        self.assertEqual(rows[1]['xyE7'], [])
        self.assertEqual(report['storedOriginalReasonCounts'], {5: 1, 8: 1})

    def test_all_eligible_empty_selection_is_a_complete_gzip(self):
        report, rows = self.run_capture([(10, 50., 0., 1, 2)], [0, 1], [0, 0, 1, 0])
        self.assertEqual(rows, [])
        self.assertEqual(report['independentAudit']['allWayRowsChecked'], 1)

    def test_bad_way_offsets_and_source_indices_refuse(self):
        for ways, refs in [([(10, 0., 0., 6 << 8, 3)], [0, 1]), ([(10, 0., 0., 6 << 8, 2)], [0, 2])]:
            with self.assertRaises(AssertionError):
                self.run_capture(ways, refs, [0, 0, 1, 0])

    def test_invalid_direction_flags_and_coordinate_domains_refuse(self):
        with self.assertRaises(AssertionError):
            self.run_capture([(10, float('nan'), 0., 6 << 8, 1)], [0], [0, 0])
        with self.assertRaises(AssertionError):
            self.run_capture([(10, 50., 0., 0, 1)], [0], [0, 0])
        with self.assertRaises(AssertionError):
            self.run_capture([(10, 0., 0., 6 << 8, 1)], [0], [1800000001, 0])

    def test_independent_audit_rejects_forged_coordinates_and_extra_records(self):
        ways, refs, xy = [(10, 0., 0., 6 << 8, 1)], [0], [10, 20]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'geometries.jsonl.gz'
            capture(ways, refs, xy, set(), path)
            raw = gzip.decompress(path.read_bytes())
            row = json.loads(raw); row['xyE7'][0][0] += 1
            path.write_bytes(gzip.compress((json.dumps(row)+'\n').encode()))
            with self.assertRaises(AssertionError):
                audit(ways, refs, xy, set(), path)
            path.write_bytes(gzip.compress(raw+raw))
            with self.assertRaises(AssertionError):
                audit(ways, refs, xy, set(), path)


if __name__ == '__main__':
    unittest.main()
