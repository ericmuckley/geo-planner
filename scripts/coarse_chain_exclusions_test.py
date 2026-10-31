"""Synthetic raw-level and frozen-exclusion accounting, without chain search."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analyze_chain_exclusions import aggregate, analyze, cohorts, level_profile, measurements, overlap
from analyze_timing_cache import Output, cache_match, prepare_row
from analyze_timing_compatibility import support
from coarse_chain_exclusions_audit import audit, reference_aggregate, reference_level, reference_measure
from coarse_timing_chains import make_nodes, row_metadata
from coarse_timing_chains_test import connected
from coarse_timing_input import PilotError
from coarse_timing_parquet import MatchIndex


def fixture(root):
    inputs = root / 'inputs'; inputs.mkdir()
    paths = {k: inputs / (k + '.json') for k in ['segments', 'scopes', 'rows', 'chains', 'support', 'matches', 'proposal', 'previousReport']}
    box = [-.01, -.01, .02, .01]
    windows = [{'id': 'a', 'bbox': box}, {'id': 'empty', 'bbox': [1, 1, 2, 2]}]
    source_rows = [connected('a', [0, 0], [.005, 0], 'start', 'join'),
        connected('b', [.005, 0], [.01, 0], 'join', 'end'),
        connected('c', [.002, 0], [.006, 0], 'start', 'other', level_rules=[{'value': 0, 'between': None}])]
    metadata, prepared = [], []
    with paths['segments'].open('wb') as source, paths['scopes'].open('w') as scopes, paths['rows'].open('w') as rows:
        for ordinal, row in enumerate(source_rows):
            raw = (json.dumps(row) + '\n').encode(); source.write(raw)
            saved, slim = prepare_row(row, windows); slim['_ordinal'] = ordinal; prepared.append(slim)
            scope = {'ordinal': ordinal, 'id': row['id'], 'version': row['version'], 'frozenLimit': saved['limit'],
                'frozenSpeedOnlyLimit': saved['speedOnlyLimit'], 'fieldsSha256': saved['fieldsSha256'],
                'rawLineSha256': hashlib.sha256(raw).hexdigest(), 'memberships': saved['memberships'],
                'rawSpeedLimits': None, 'rawAccessRestrictions': None}
            scopes.write(json.dumps(scope) + '\n')
            meta = row_metadata(row, scope); rows.write(json.dumps(meta) + '\n'); metadata.append(meta)
    sample_count = 0
    with paths['chains'].open('w') as chains, paths['support'].open('w') as supports, paths['matches'].open('wb') as matches:
        for arc, window in enumerate(windows):
            spans = [([0, 0], [.01, 0], 99.)] if arc == 0 else [([1.1, 1.1], [1.11, 1.1], 10.)]
            index = MatchIndex(prepared if arc == 0 else [], window['bbox'])
            previous = cache_match(index, spans)
            previous.update(windowId=window['id'], arc=arc, sourceClassKph=105 if arc == 0 else 85, sourceSpans=spans)
            encoded = (json.dumps(previous) + '\n').encode(); matches.write(encoded)
            saved_support = support(index, spans)
            saved_support.update(windowId=window['id'], arc=arc, savedMatchLineSha256=hashlib.sha256(encoded).hexdigest())
            encoded = json.dumps(saved_support) + '\n'; supports.write(encoded)
            points = [[a[0] + (b[0] - a[0]) * (i + .5) / n, a[1] + (b[1] - a[1]) * (i + .5) / n]
                for (a, b, _), n in [(spans[0], saved_support['samples'][0][2])] for i in range(n)]
            nodes, excluded = make_nodes(metadata, saved_support['samples'], points, window['bbox'])
            sample_count += len(points)
            candidates = [{'rowOrdinals': [0, 1], 'memberParserStatuses': ['missing', 'missing']}] if arc == 0 else []
            chain = {'windowId': window['id'], 'arc': arc, 'sourceClassKph': previous['sourceClassKph'],
                'sourceKm': previous['sourceKm'], 'savedSupportLineSha256': hashlib.sha256(encoded.encode()).hexdigest(),
                'oldStatus': previous['status'], 'baselineProvisionalEligibleKm': previous['provisionalStaticLimitMatchedKm'],
                'sourceStatus': 'incomplete_after_capture_stop', 'nodes': list(nodes.values()), 'excludedRows': excluded,
                'candidates': candidates, 'status': 'unresolved_with_candidates' if arc == 0 else 'unmeasured_empty_cache',
                'supportsHypothesis': arc == 0, 'searchCapped': False}
            chains.write(json.dumps(chain) + '\n')
    paths['proposal'].write_text(json.dumps({'selection': {'windows': windows}}))
    prior = {'frozenLimitStatusCounts': {'missing': 3}, 'scopeRowCounts': {'speedRows': 0, 'accessRows': 0},
        'publisherGeometryKm': {'a': 0., 'empty': 0.}, 'windows': [{'id': 'a', 'cachedRows': 3}, {'id': 'empty', 'cachedRows': 0}],
        'allWindows': {'sourceKm': 109., 'recordsWithCandidates': 1, 'statusCounts': {'unresolved_with_candidates': 1, 'unmeasured_empty_cache': 1},
            'candidateChains': 1, 'formerlyAbsentUncappedWithChain': 1, 'cappedRecords': 0}}
    paths['previousReport'].write_text(json.dumps(prior))
    plan = {'expectedRows': 3, 'expectedMatches': 2, 'expectedSamples': sample_count, 'expectedWindows': 2, 'maxLineBytes': 4194304}
    return plan, paths


class ExclusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def test_level_categories_keep_zero_distinct_from_missing(self):
        cases = [(None, 'missing'), ([], 'missing'), ([{'value': 0}], 'uniform_zero'),
            ([{'value': -1}], 'uniform_nonzero'), ([{'value': 0}, {'value': 1}], 'mixed'),
            ([{'value': 0, 'between': [.2, .8]}], 'partial'),
            ([{'value': 0, 'when': {'during': 'night'}}], 'unsupported_fields')]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(level_profile(raw)['category'], expected)
                self.assertEqual(level_profile(raw), reference_level(raw))

    def test_malformed_boolean_string_and_interval_do_not_become_zero(self):
        for raw in [{}, '0', [None], [{'value': False}], [{'value': '0'}], [{'value': float('nan')}],
                    [{'value': 0, 'between': [1, 0]}], [{'between': None}]]:
            with self.subTest(raw=raw):
                self.assertEqual(level_profile(raw)['category'], 'malformed')
                self.assertEqual(level_profile(raw), reference_level(raw))

    def test_partial_and_extra_fields_preserve_underlying_zero_value(self):
        raw = [{'value': 0, 'between': [.2, .8], 'extra': 'unknown'}]
        result = level_profile(raw)
        self.assertEqual(result['category'], 'unsupported_fields')
        self.assertEqual(result['valueCategory'], 'uniform_zero')
        self.assertIn('partial_intervals', result['flags'])
        self.assertIn('extra', result['fieldNames'])

    def test_overlapping_and_touching_level_intervals_are_separate(self):
        self.assertNotIn('overlapping_intervals', level_profile([{'value': 0, 'between': [0, .5]}, {'value': 0, 'between': [.5, 1]}])['flags'])
        raw = [{'value': 0, 'between': [0, .6]}, {'value': 1, 'between': [.5, 1]}]
        self.assertIn('overlapping_intervals', level_profile(raw)['flags'])
        self.assertEqual(level_profile(raw), reference_level(raw))

    def test_base_level_reason_is_not_replaced_by_new_measurements(self):
        row = {'endpoints': [[0, 0], [.01, 0]], 'baseReasons': ['unsupported_level_rules']}
        result = measurements(row, [0], [[.005, 0]], [-1, -1, 1, 1])
        self.assertIn('endpoint_not_near_own_samples', result['flags'])
        self.assertFalse(result['frozenProgressApplied'])
        self.assertIsNone(result['frozenProgressReason'])
        self.assertEqual(result, reference_measure(row, [0], [[.005, 0]], [-1, -1, 1, 1]))

    def test_frozen_distance_precedes_tie_and_outside_precedes_progress(self):
        row = {'endpoints': [[0, 0], [.01, 0]], 'baseReasons': []}
        result = measurements(row, [0], [[.005, 0]], [-1, -1, 1, 1])
        self.assertEqual(result['frozenProgressReason'], 'endpoint_not_near_own_samples')
        outside = measurements(row, [0], [[.005, 0]], [-.001, -.001, .005, .001])
        self.assertFalse(outside['frozenProgressApplied'])
        self.assertIsNone(outside['frozenProgressReason'])

    def test_short_endpoint_tie_and_missing_geometry_stay_unknown(self):
        row = {'endpoints': [[.00499, 0], [.00501, 0]], 'baseReasons': []}
        result = measurements(row, [0], [[.005, 0]], [-1, -1, 1, 1])
        self.assertEqual(result['frozenProgressReason'], 'nonprogressing_or_tied_endpoints')
        missing = measurements({'endpoints': [], 'baseReasons': ['multipart_geometry']}, [0], [[0, 0]], [-1, -1, 1, 1])
        self.assertEqual(missing['measuredProgress'], 'unavailable_geometry')

    def test_sample_and_endpoint_overlap_do_not_imply_a_join(self):
        row = {'endpointIds': ['same-id', 'other']}
        result = overlap([0, 1], row, {1, 2}, {'same-id'}, [90., 9., 1.], True)
        self.assertEqual(result['kind'], 'sample_and_endpoint')
        self.assertEqual(result['sharedSampleIncidenceKm'], 9.)
        self.assertNotIn('canJoin', result)
        self.assertEqual(overlap([0], row, {2}, {'same-id'}, [90., 9., 1.], True)['kind'], 'endpoint_only')
        self.assertEqual(overlap([0], row, {0}, set(), [90.], True)['kind'], 'sample_only')
        self.assertEqual(overlap([0], row, set(), set(), [90.], True)['kind'], 'neither')

    def test_cohorts_overlap_without_dropping_empty_windows(self):
        base = {'candidates': [{}], 'supportsHypothesis': True, 'oldStatus': 'absent_in_cache'}
        self.assertEqual(cohorts(base, 1), ['all', 'with_cache', 'candidate_bearing', 'formerly_absent_positive', 'baseline_absent'])
        self.assertIn('empty_cache', cohorts({**base, 'candidates': [], 'supportsHypothesis': False}, 0))

    def test_end_to_end_preserves_original_outcomes_and_audit_rejects_tampering(self):
        plan, paths = fixture(self.root)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        with contextlib.redirect_stdout(io.StringIO()): analyze(plan, output, paths)
        audit(plan, output, paths)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertEqual(report['retainedLevelCategories'], {'missing': 2, 'uniform_zero': 1})
        self.assertEqual(report['cohorts']['candidate_bearing']['excludedIncidences'], 1)
        self.assertEqual(report['cohorts']['empty_cache']['arcCount'], 1)
        self.assertEqual(report['matcherEnumerationsPerformed'], 0)
        self.assertFalse(report['originalFeasibilityQualified'])
        path = self.root / 'exclusions.jsonl'; records = [json.loads(v) for v in path.read_text().splitlines()]
        records[0]['excluded'][0]['measurements']['endpointDistancesKm'][0] = 100
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        with self.assertRaises(PilotError): audit(plan, output, paths)

    def test_repeated_row_incidences_do_not_become_unique_roads_or_coverage(self):
        plan, paths = fixture(self.root)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        analyze(plan, output, paths)
        records = [json.loads(v) for v in (self.root / 'exclusions.jsonl').read_text().splitlines()]
        doubled = [records[0], records[0]]
        result = aggregate(doubled)
        self.assertEqual(result['excludedIncidences'], 2)
        self.assertEqual(result['uniqueExcludedPublisherIds'], 1)
        self.assertEqual(result['reasonIncidences']['unsupported_level_rules'], 2)
        self.assertEqual(result['reasonUniquePublisherIds']['unsupported_level_rules'], 1)
        self.assertEqual(result, reference_aggregate(doubled))

    def test_audit_does_not_replay_join_or_chain_enumeration(self):
        plan, paths = fixture(self.root)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        forbidden = AssertionError('Completed matcher must not be replayed')
        with patch('coarse_timing_chains.search_chains', side_effect=forbidden), patch('coarse_timing_chains.adjacency', side_effect=forbidden), patch('coarse_timing_chains_audit.reference_search', side_effect=forbidden):
            analyze(plan, output, paths)
            audit(plan, output, paths)


if __name__ == '__main__':
    unittest.main()
