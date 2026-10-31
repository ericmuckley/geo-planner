"""Meaningful partial-data and weighted-accounting cases; no live sources."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import struct
import base64
import tempfile
import unittest
from unittest.mock import patch

from analyze_timing_cache import (Output, add_row, analyze, cache_match, clipped_km,
                                  empty_group, observations, prepare_row)
from coarse_timing_cache_audit import audit, geometry_km, interval
from coarse_timing_input import PilotError
from coarse_timing_parquet import MatchIndex, source_spans


def road(identity='a', lines=None, **extra):
    points = lines or [[0., 0.], [.01, 0.]]
    raw = struct.pack('<BII', 1, 2, len(points)) + b''.join(struct.pack('<dd', *p) for p in points)
    row = {k: None for k in ['access_restrictions', 'connectors', 'level_rules', 'prohibited_transitions',
                           'road_flags', 'sources', 'speed_limits', 'subclass', 'subclass_rules']}
    row.update(id=identity, version=1, subtype='road', **{'class': 'primary'},
               bbox={'xmin': min(p[0] for p in points), 'xmax': max(p[0] for p in points),
                     'ymin': min(p[1] for p in points), 'ymax': max(p[1] for p in points)},
               geometryWkbBase64=base64.b64encode(raw).decode())
    return {**row, **extra}


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.windows = [{'id': 'a', 'bbox': [-.01, -.01, .02, .01]}, {'id': 'b', 'bbox': [1, 1, 2, 2]}]

    def test_access_priority_does_not_hide_raw_speed_scopes(self):
        row = road(speed_limits=[{'max_speed': {'value': 50, 'unit': 'mph'},
                                'between': [.2, .8], 'when': {'heading': 'forward', 'during': 'Mo-Fr'},
                                'is_max_speed_variable': True}], access_restrictions=[{'access_type': 'denied'}])
        record, _ = prepare_row(row, self.windows)
        self.assertEqual(record['limit']['status'], 'access_scoped_or_restricted')
        for flag in ['partial_speed_rule', 'conditional_speed_rule', 'directional_speed_rule', 'variable_speed_rule']:
            self.assertIn(flag, record['observations'])
        self.assertEqual(record['speedOnlyLimit']['status'], 'partial_scope')

    def test_missing_and_malformed_attributes_stay_visible(self):
        self.assertIn('speed_limits_missing', observations(road()))
        self.assertIn('malformed_speed_rule', observations(road(speed_limits=[None])))
        self.assertIn('unsupported_speed_unit', observations(road(speed_limits=[{'max_speed': {'value': 1, 'unit': 'knots'}}])))
        self.assertIn('no_explicit_maximum_rule', observations(road(speed_limits=[{}])))

    def test_raw_fields_preserved_and_hash_changes_on_scoped_property(self):
        row = road(sources=[{'dataset': 'x', 'license': 'y'}])
        before = deepcopy(row)
        record, _ = prepare_row(row, self.windows)
        self.assertEqual(row, before)
        changed, _ = prepare_row({**row, 'level_rules': [{'between': [.2, .4], 'value': 1}]}, self.windows)
        self.assertNotEqual(record['fieldsSha256'], changed['fieldsSha256'])

    def test_bbox_candidate_without_clipped_geometry_is_zero_length(self):
        row = road(lines=[[-1, .02], [1, .02]], bbox={'xmin': -1, 'xmax': 1, 'ymin': 0, 'ymax': .02})
        record, _ = prepare_row(row, self.windows)
        self.assertEqual(record['memberships'], [{'windowId': 'a', 'clippedGeometryKm': 0.}])

    def test_malformed_geometry_keeps_identity_and_scoped_rule(self):
        record, slim = prepare_row(road(geometryWkbBase64='bad!'), self.windows)
        self.assertEqual(record['id'], 'a')
        self.assertEqual(record['geometryStatus'], 'malformed_geometry')
        self.assertEqual(slim['_lines'], [])
        self.assertEqual(record['limit']['status'], 'missing')

    def test_disconnected_geometry_does_not_gain_gap_length(self):
        lines = [[[0, 0], [.001, 0]], [[.009, 0], [.01, 0]]]
        box = [-1, -1, 1, 1]
        self.assertLess(clipped_km(lines, box), .23)
        self.assertAlmostEqual(clipped_km(lines, box), geometry_km(lines, box))

    def test_clipped_geometry_independent_audit_handles_diagonals_and_boundaries(self):
        for a, b, box in [([-1, -1], [2, 2], [0, 0, 1, 1]), ([0, 0], [1, 0], [0, 0, 1, 1]),
                          ([0, 2], [1, 2], [0, 0, 1, 1]), ([2, 0], [-1, 0], [0, -1, 1, 1])]:
            with self.subTest(a=a):
                self.assertAlmostEqual(clipped_km([[a, b]], box), geometry_km([[a, b]], box))
        self.assertIsNone(interval([0, 0], [0, 0], [1, 1, 2, 2]))

    def test_single_candidate_becomes_ambiguous_when_unseen_parallel_arrives(self):
        record, slim = prepare_row(road(speed_limits=[{'max_speed': {'value': 80, 'unit': 'km/h'}}]), self.windows)
        spans = [([0, 0], [.01, 0], 99.)]
        result = cache_match(MatchIndex([slim], self.windows[0]['bbox']), spans)
        self.assertEqual(result['status'], 'single_in_cache')
        self.assertFalse(result['sourceComplete'])
        self.assertAlmostEqual(result['provisionalStaticLimitMatchedKm'], 99)
        _, parallel = prepare_row(road('b', lines=[[0, .0001], [.01, .0001]]), self.windows)
        changed = cache_match(MatchIndex([slim, parallel], self.windows[0]['bbox']), spans)
        self.assertEqual(changed['status'], 'ambiguous_in_cache')
        self.assertEqual(changed['provisionalStaticLimitMatchedKm'], 0.)

    def test_absent_candidate_is_not_complete_or_zero_source_denominator(self):
        result = cache_match(MatchIndex([], self.windows[0]['bbox']), [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['status'], 'absent_in_cache')
        self.assertEqual(result['sourceKm'], 99.)
        self.assertFalse(result['sourceComplete'])

    def test_original_census_weights_not_chord_length(self):
        data = {'nodeCoordinates': [0, 0, .01, 0], 'arcFrom': [0], 'arcTo': [1], 'arcRoadKm': [99],
                'arcInteriorOffsets': [0, 0], 'arcByteOffsets': [0, 0], 'geometryBytes': b'', 'interiorSourceKm': [],
                'cellIds': [10], 'cellArcOffsets': [0, 1], 'cellArcs': [0]}
        result = source_spans(data, {'bounds': [0, -.01, .1, .1], 'step': .01, 'width': 10, 'height': 10}, [.002, -.01, .008, .01])
        self.assertAlmostEqual(sum(s[2] for s in result[0][1]), 59.4)

    def test_window_and_class_totals_preserve_rows_scopes_and_weight(self):
        record, _ = prepare_row(road(), self.windows)
        group = empty_group()
        add_row(group, record, 2.5)
        add_row(group, record, 0.)
        self.assertEqual(group['bboxCandidateRows'], 2)
        self.assertEqual(group['rowsWithClippedGeometry'], 1)
        self.assertEqual(group['limitStatusCounts'], {'missing': 2})
        self.assertEqual(group['limitStatusGeometryKm'], {'missing': 2.5})
        self.assertEqual(group['observationGeometryKm']['speed_limits_missing'], 2.5)

    def test_output_guards_preserve_existing_bytes_and_check_time(self):
        now = [0.]
        output = Output(self.root, 4, 5, clock=lambda: now[0])
        output.write('a', b'abc')
        with self.assertRaises(PilotError): output.write('a', b'xx', append=True)
        with self.assertRaises(FileExistsError): output.write('a', b'x')
        with self.assertRaises(PilotError): output.write('../escape', b'x')
        now[0] = 6
        with self.assertRaises(PilotError): output.write('b', b'x')
        self.assertEqual((self.root / 'a').read_bytes(), b'abc')

    def test_duplicate_identity_stops_without_replacing_partial_ledger(self):
        path = self.root / 'source.jsonl'
        path.write_text((json.dumps(road()) + '\n') * 2)
        proposal = {'selection': {'windows': self.windows}, 'columns': [k for k in road() if k != 'geometryWkbBase64'] + ['geometry']}
        output = Output(self.root, 1024 ** 2, 5)
        with self.assertRaises(PilotError): analyze({'expectedRows': 2, 'maxLineBytes': 65536}, output, path, proposal, {})
        self.assertEqual(len((self.root / 'rows.jsonl').read_text().splitlines()), 1)

    def test_end_to_end_keeps_empty_windows_and_audit_rejects_changed_source_weights(self):
        windows = [self.windows[0]] + [{'id': f'empty-{i}', 'bbox': [i, 1, i + .1, 1.1]} for i in range(1, 21)]
        row = road(speed_limits=[{'max_speed': {'value': 80, 'unit': 'km/h'}}])
        path = self.root / 'source.jsonl'
        path.write_text(json.dumps(row) + '\n')
        proposal = {'selection': {'windows': windows}, 'columns': [k for k in row if k != 'geometryWkbBase64'] + ['geometry']}
        grid = {'bounds': [0, -.01, .1, .1], 'step': .01, 'width': 10, 'height': 10}
        data = {'nodeCoordinates': [0, 0, .01, 0], 'arcFrom': [0], 'arcTo': [1], 'arcRoadKm': [99], 'arcSpeedKph': [105],
                'arcInteriorOffsets': [0, 0], 'arcByteOffsets': [0, 0], 'geometryBytes': b'', 'interiorSourceKm': [],
                'cellIds': [10], 'cellArcOffsets': [0, 1], 'cellArcs': [0]}
        plan = {'expectedRows': 1, 'maxLineBytes': 65536, 'grid': grid}
        output = Output(self.root, 1024 ** 2, 5)
        with contextlib.redirect_stdout(io.StringIO()):
            analyze(plan, output, path, proposal, data)
        with patch('coarse_timing_cache_audit.Path', side_effect=lambda p: path if p == '/cache/segments.jsonl' else Path(p)):
            audit(plan, output, proposal, data)
            result = json.loads((self.root / 'report.json').read_text())
            self.assertEqual(len(result['windows']), 21)
            self.assertEqual(result['completedSourceWindows'], 0)
            self.assertFalse(result['originalFeasibilityQualified'])
            self.assertEqual(result['windows'][1]['publisherTotals']['bboxCandidateRows'], 0)
            match_path = self.root / 'matches.jsonl'
            match = json.loads(match_path.read_text())
            match['sourceKm'] = 98
            match_path.write_text(json.dumps(match) + '\n')
            with self.assertRaises(PilotError): audit(plan, output, proposal, data)


if __name__ == '__main__':
    unittest.main()
