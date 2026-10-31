"""Synthetic geometric-union and raw-scope checks; no source acquisition."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analyze_timing_cache import Output, cache_match, prepare_row
from analyze_timing_compatibility import analyze, leaves, scope_profile, support, union_status
from coarse_timing_cache_test import road
from coarse_timing_compatibility_audit import aligned, audit
from coarse_timing_input import PilotError
from coarse_timing_parquet import MatchIndex


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.box = [-.01, -.01, .02, .01]
        self.windows = [{'id': 'a', 'bbox': self.box}, {'id': 'empty', 'bbox': [1, 1, 2, 2]}]

    def index(self, rows):
        slim = []
        for ordinal, row in enumerate(rows):
            _, ready = prepare_row(row, self.windows)
            ready['_ordinal'] = ordinal; slim.append(ready)
        return MatchIndex(slim, self.box)

    def test_fragmented_union_is_not_a_single_candidate(self):
        index = self.index([road('a', [[0, 0], [.0049, 0]]), road('b', [[.0051, 0], [.01, 0]])])
        result = support(index, [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['candidateOrdinals'], [])
        self.assertAlmostEqual(result['unionAlignedKm'], 99)
        self.assertEqual(union_status('absent_in_cache', 99, result['unionAlignedKm']), 'union_aligned_without_single_candidate')

    def test_parallel_competitors_do_not_double_union_weight(self):
        index = self.index([road('a'), road('b', [[0, .0001], [.01, .0001]])])
        result = support(index, [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['candidateOrdinals'], [0, 1])
        self.assertAlmostEqual(result['unionAlignedKm'], 99)
        self.assertEqual(union_status('ambiguous_in_cache', 99, 99), 'existing_ambiguous_in_cache')

    def test_crossing_geometry_and_far_parallel_do_not_support(self):
        index = self.index([road('a', [[.005, -.005], [.005, .005]]), road('b', [[0, .001], [.01, .001]])])
        result = support(index, [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['unionAlignedKm'], 0)
        self.assertEqual(union_status('absent_in_cache', 99, 0), 'no_aligned_cached_geometry')
        self.assertFalse(aligned([.005, 0], [0, 0], [.01, 0], [.005, -.005], [.005, .005]))

    def test_partial_geometry_and_unsupported_role_are_preserved(self):
        index = self.index([road('a', [[0, 0], [.003, 0]], **{'class': 'footway'})])
        result = support(index, [([0, 0], [.01, 0], 99.)])
        self.assertGreater(result['unionAlignedKm'], 0)
        self.assertEqual(union_status('absent_in_cache', 99, result['unionAlignedKm']), 'partial_aligned_cached_geometry')
        self.assertEqual(index.rows[0]['_limit']['status'], 'unsupported_road_role')

    def test_original_nonuniform_source_weights_survive_sampling(self):
        index = self.index([road('a', [[0, 0], [.004, 0]])])
        spans = [([0, 0], [.004, 0], 90.), ([.006, 0], [.01, 0], 9.)]
        result = support(index, spans)
        self.assertAlmostEqual(result['sourceKm'], 99)
        self.assertAlmostEqual(result['unionAlignedKm'], 90)
        self.assertAlmostEqual(sum(s[3] for s in result['samples']), 99)

    def test_empty_cache_preserves_all_source_weights(self):
        result = support(self.index([]), [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['candidateOrdinals'], [])
        self.assertAlmostEqual(sum(s[3] for s in result['samples']), 99)
        self.assertEqual(result['unionAlignedKm'], 0)

    def test_fixed_eighty_percent_partition_and_original_single_status(self):
        self.assertEqual(union_status('absent_in_cache', 100, 80), 'union_aligned_without_single_candidate')
        self.assertEqual(union_status('absent_in_cache', 100, 79.9), 'partial_aligned_cached_geometry')
        result = support(self.index([road('a', [[.01, 0], [0, 0]])]), [([0, 0], [.01, 0], 99.)])
        self.assertEqual(result['candidateOrdinals'], [0])
        self.assertEqual(union_status('single_in_cache', 99, result['unionAlignedKm']), 'existing_single_in_cache')

    def test_touching_rule_intervals_are_not_overlapping(self):
        profile = scope_profile([{'between': [0, .5], 'access_type': 'allowed'},
                                 {'between': [.5, 1], 'access_type': 'denied'}], 'access')
        self.assertIn('multiple_access_types', profile['flags'])
        self.assertNotIn('overlapping_between_intervals', profile['flags'])

    def test_disconnected_parts_never_gain_support_across_gap(self):
        index = self.index([road('a')])
        index.rows[0]['_lines'] = [[[0, 0], [.002, 0]], [[.008, 0], [.01, 0]]]
        index = MatchIndex(index.rows, self.box)
        result = support(index, [([0, 0], [.01, 0], 99.)])
        self.assertLess(result['unionAlignedKm'], 50)

    def test_raw_speed_scope_flags_overlap_without_access_admission(self):
        rules = [{'between': [.1, .8], 'is_max_speed_variable': True,
            'when': {'heading': 'forward', 'vehicle': [{'dimension': 'weight'}], 'during': 'Mo-Fr'},
            'max_speed': {'unit': 'mph', 'value': 50}}, {'max_speed': {'unit': 'km/h', 'value': 70}}]
        profile = scope_profile(rules, 'speed')
        for flag in ['partial_between', 'variable_speed', 'when_heading', 'when_vehicle', 'when_during',
                     'conditional_scope', 'multiple_maximum_values', 'overlapping_between_intervals']:
            self.assertIn(flag, profile['flags'])

    def test_access_allowed_and_different_headings_remain_raw_scopes(self):
        rules = [{'access_type': 'allowed', 'when': {'heading': 'forward'}},
                 {'access_type': 'denied', 'when': {'heading': 'backward'}}]
        profile = scope_profile(rules, 'access')
        self.assertIn('multiple_access_types', profile['flags'])
        self.assertIn('when_heading', profile['flags'])
        self.assertNotIn('usable', profile)

    def test_missing_malformed_units_and_ranges_are_explicit(self):
        self.assertFalse(scope_profile(None, 'speed')['present'])
        self.assertIn('malformed_rules', scope_profile({}, 'speed')['flags'])
        self.assertIn('malformed_rules', scope_profile('bad', 'speed')['flags'])
        flags = scope_profile([None, {'between': [1, 0], 'when': 1, 'is_max_speed_variable': 'yes',
                  'max_speed': {'unit': 'knots', 'value': 3}}], 'speed')['flags']
        for flag in ['malformed_rule', 'malformed_between', 'malformed_when', 'malformed_variable_flag', 'unsupported_unit']:
            self.assertIn(flag, flags)

    def test_raw_leaf_inventory_keeps_units_vehicle_and_time_values(self):
        result = dict(leaves([{'max_speed': {'value': 35, 'unit': 'mph'}, 'when': {'vehicle': ['motorcar'], 'during': 'Mo-Fr'}}]))
        self.assertEqual(result['[].max_speed.unit'], '"mph"')
        self.assertEqual(result['[].when.vehicle[]'], '"motorcar"')
        self.assertEqual(result['[].when.during'], '"Mo-Fr"')

    def test_end_to_end_and_independent_sample_tamper_detection(self):
        rows = [road('a', [[0, 0], [.0049, 0]]), road('b', [[.0051, 0], [.01, 0]])]
        inputs = self.root / 'inputs'; inputs.mkdir()
        paths = {k: inputs / (k + '.json') for k in ['segments', 'rows', 'matches', 'proposal', 'report']}
        prepared = []
        with paths['segments'].open('wb') as raw_stream, paths['rows'].open('w') as ledger:
            for ordinal, row in enumerate(rows):
                raw = (json.dumps(row) + '\n').encode(); raw_stream.write(raw)
                saved, slim = prepare_row(row, self.windows); saved['rawLineSha256'] = hashlib.sha256(raw).hexdigest()
                ledger.write(json.dumps(saved) + '\n'); slim['_ordinal'] = ordinal; prepared.append(slim)
        old = cache_match(MatchIndex(prepared, self.box), [([0, 0], [.01, 0], 99.)])
        old.update(windowId='a', arc=0, sourceClassKph=105, sourceSpans=[([0, 0], [.01, 0], 99.)])
        paths['matches'].write_text(json.dumps(old) + '\n')
        paths['proposal'].write_text(json.dumps({'selection': {'windows': self.windows}}))
        paths['report'].write_text(json.dumps({'limitStatusCounts': {'missing': 2},
            'fieldNonemptyCounts': {'speed_limits': 0, 'access_restrictions': 0},
            'windows': [{'id': w['id'], 'publisherTotals': {'clippedGeometryKm': 0.}} for w in self.windows]}))
        plan = {'expectedRows': 2, 'expectedMatches': 1, 'expectedWindows': 2, 'maxLineBytes': 4194304}
        output = Output(self.root, 1024 ** 2, 5)
        with contextlib.redirect_stdout(io.StringIO()): analyze(plan, output, paths)
        audit(plan, output, paths)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(len(report['windows']), 2)
        self.assertEqual(report['windows'][1]['cachedRows'], 0)
        self.assertEqual(report['completedSourceWindows'], 0)
        self.assertFalse(report['originalFeasibilityQualified'])
        path = self.root / 'support.jsonl'; result = json.loads(path.read_text())
        result['samples'][0][4] = []; path.write_text(json.dumps(result) + '\n')
        with self.assertRaises(PilotError): audit(plan, output, paths)


if __name__ == '__main__':
    unittest.main()
