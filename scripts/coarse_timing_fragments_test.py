"""Synthetic fragment geometry and control tests; no real road-data replay."""
import base64
from copy import deepcopy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analyze_timing_cache import Output, cache_match, prepare_row
from analyze_timing_compatibility import support
from coarse_timing_cache_test import road
from coarse_timing_chains import analyze as old_analyze, make_nodes, row_metadata
from coarse_timing_chains_test import node
from coarse_timing_fragments import (analyze, cumulative_lengths, fragment_links, fragment_status,
    interval_in_window, make_fragments, nearest_projection, search_fragments)
from coarse_timing_fragments_audit import audit, equivalent, reference_fragments, reference_search
from coarse_timing_input import PilotError
from coarse_timing_parquet import MatchIndex, decode_lines


def connected(identity, points, enter='a', exit_='b', **extra):
    return road(identity, points, connectors=[{'at': 0., 'connector_id': enter}, {'at': 1., 'connector_id': exit_}], **extra)


class FragmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.box = [-.01, -.01, .02, .01]
        self.windows = [{'id': 'a', 'bbox': self.box}, {'id': 'empty', 'bbox': [1, 1, 2, 2]}]
        self.points = [[(.5 + i) * .0002, 0.] for i in range(50)]
        self.tangents = [[[0., 0.], [.01, 0.]]] * 50

    def fragments(self, rows, membership=None, points=None, tangents=None, box=None, old=True):
        metadata, lines = [], []
        for ordinal, row in enumerate(rows):
            saved, _ = prepare_row(row, self.windows)
            scope = {'ordinal': ordinal, 'frozenLimit': saved['limit'], 'frozenSpeedOnlyLimit': saved['speedOnlyLimit'],
                'rawLineSha256': 'fixture', 'fieldsSha256': saved['fieldsSha256'], 'memberships': saved['memberships']}
            metadata.append(row_metadata(row, scope)); lines.append(decode_lines(base64.b64decode(row['geometryWkbBase64']))[0])
        points = self.points if points is None else points
        tangents = self.tangents if tangents is None else tangents
        samples = [[0, i, len(points), 1., list(range(len(rows))) if membership is None else membership[i]] for i in range(len(points))]
        full, _ = make_nodes(metadata, samples, points, box or self.box) if old else ({}, [])
        args = metadata, lines, samples, points, tangents, box or self.box, list(full.values())
        result = make_fragments(*args)
        expected = reference_fragments(*args)
        for actual, reference in zip(result, expected): equivalent(actual, reference)
        return result, metadata

    def search(self, nodes, weights=None, maximum_rows=64, maximum_states=4096):
        weights = [1.] * 50 if weights is None else weights
        result = search_fragments(nodes, weights, maximum_rows, maximum_states)
        equivalent(result, reference_search(nodes, weights, maximum_rows, maximum_states))
        return result

    def test_overhanging_terminal_endpoints_can_be_cut_inside_window(self):
        rows = [connected('a', [[-.001, 0], [.011, 0]])]
        (nodes, issues, _), _ = self.fragments(rows, box=[0., -.001, .01, .001])
        self.assertEqual(set(nodes), {'0/both'})
        result = self.search(nodes)
        self.assertEqual(len(result['candidates']), 1)
        self.assertTrue(result['candidates'][0]['hasTerminalCut'])
        self.assertEqual(result['candidates'][0]['supportedKm'], 50.)
        self.assertIsNone(nodes['0/both']['entryId']); self.assertIsNone(nodes['0/both']['exitId'])
        self.assertTrue(issues)  # Uncut variants remain ineligible, with reasons.

    def test_split_connected_path_preserves_supported_union(self):
        rows = [connected('a', [[-.001, 0], [.005, 0]], 'a', 'join'),
                connected('b', [[.005, 0], [.011, 0]], 'join', 'b')]
        membership = [[0] if i < 25 else [1] for i in range(50)]
        (nodes, _, _), _ = self.fragments(rows, membership)
        candidates = self.search(nodes)['candidates']
        self.assertEqual([c['rowOrdinals'] for c in candidates], [[0, 1]])
        self.assertEqual(candidates[0]['coveredSampleMaskHex'], hex(2 ** 50 - 1))
        self.assertEqual(nodes['0/start']['exitId'], 'join')
        self.assertEqual(nodes['1/end']['entryId'], 'join')

    def test_reversal_and_collinear_densification_preserve_geometry(self):
        base = [[-.001, 0], [.011, 0]]
        (forward, _, _), _ = self.fragments([connected('a', base)])
        (reverse, _, _), _ = self.fragments([connected('a', base[::-1], 'b', 'a')])
        (dense, _, _), _ = self.fragments([connected('a', [base[0], [.003, 0], [.005, 0], base[-1]])])
        for nodes in (reverse, dense):
            self.assertEqual(self.search(nodes)['candidates'], self.search(forward)['candidates'])
            equivalent(nodes['0/both']['entryPoint'], forward['0/both']['entryPoint'])
            equivalent(nodes['0/both']['exitPoint'], forward['0/both']['exitPoint'])
        self.assertAlmostEqual(reverse['0/both']['entryFraction'], 1 - forward['0/both']['entryFraction'])

    def test_shared_vertex_ties_and_duplicate_vertices_are_harmless(self):
        line = [[-.001, 0], [.005, 0], [.005, 0], [.011, 0]]
        p = nearest_projection([.005, 0], [[0, 0], [.01, 0]], line, cumulative_lengths(line))
        self.assertAlmostEqual(p['fraction'], .5)

    def test_disconnected_or_spatially_separated_join_does_not_connect(self):
        for other, y in [('different', 0.), ('join', .0005)]:
            rows = [connected('a', [[-.001, 0], [.005, 0]], 'a', 'join'),
                    connected('b', [[.005, y], [.011, 0]], other, 'b')]
            (nodes, _, _), _ = self.fragments(rows, [[0] if i < 25 else [1] for i in range(50)])
            self.assertEqual(self.search(nodes)['candidates'], [])

    def test_clipped_endpoints_never_become_internal_connectors(self):
        rows = [connected('a', [[-.001, 0], [.006, 0]], 'a', 'join'),
                connected('b', [[.004, 0], [.011, 0]], 'join', 'b')]
        (nodes, _, _), _ = self.fragments(rows, [[0] if i < 25 else [1] for i in range(50)])
        for k, following in fragment_links(nodes).items():
            self.assertTrue(all(nodes[k]['exitId'] is not None and nodes[j]['entryId'] is not None for j in following))
        self.assertEqual(self.search(nodes)['candidates'], [])

    def test_parallel_candidates_remain_alternatives_and_far_ones_fail(self):
        rows = [connected('a', [[-.001, .0001], [.011, .0001]]), connected('b', [[-.001, -.0001], [.011, -.0001]])]
        (nodes, _, _), _ = self.fragments(rows)
        self.assertEqual(len(self.search(nodes)['candidates']), 2)
        (nodes, issues, _), _ = self.fragments([connected('far', [[-.001, .001], [.011, .001]])])
        self.assertEqual(nodes, {}); self.assertIn('projection_outside_distance', issues[0]['reasons'])

    def test_crossing_tangent_and_retraced_loop_are_unresolved(self):
        crossing = connected('cross', [[.005, -.001], [.005, .001]])
        (nodes, issues, _), _ = self.fragments([crossing], old=False)
        self.assertEqual(nodes, {}); self.assertIn('projection_outside_distance', issues[0]['reasons'])
        with self.assertRaisesRegex(PilotError, 'projection_tangent_mismatch'):
            nearest_projection([.005, 0], [[0, 0], [.01, 0]], [[.005, -.001], [.005, .001]], cumulative_lengths([[.005, -.001], [.005, .001]]))
        loop = connected('loop', [[-.001, 0], [.011, 0], [-.001, 0]])
        (nodes, issues, _), _ = self.fragments([loop], old=False)
        self.assertEqual(nodes, {}); self.assertIn('ambiguous_projection', issues[0]['reasons'])

    def test_nonmonotone_and_single_sample_progress_stay_unresolved(self):
        row = connected('a', [[-.001, 0], [.011, 0]])
        for points, reason in [([[.001, 0], [.008, 0], [.003, 0]], 'nonmonotone_or_tied_projection'),
                               ([[.001, 0], [.004, 0], [.004, 0], [.009, 0]], 'nonmonotone_or_tied_projection'),
                               ([[.005, 0]], 'insufficient_projection_progress')]:
            (nodes, issues, _), _ = self.fragments([row], points=points, tangents=self.tangents[:len(points)], old=False)
            self.assertEqual(nodes, {}); self.assertIn(reason, issues[0]['reasons'])

    def test_samples_clamped_to_an_original_endpoint_keep_ordered_support(self):
        row = connected('a', [[-.001, 0], [.005, 0]])
        points = [[.001, 0], [.0049, 0], [.005, 0], [.0051, 0]]
        (nodes, _, _), _ = self.fragments([row], points=points, tangents=self.tangents[:4], old=False)
        self.assertIn('0/start', nodes)
        self.assertTrue(self.search(nodes, [1.] * 4)['candidates'])

    def test_role_level_and_connector_filters_are_not_relaxed(self):
        base = connected('a', [[-.001, 0], [.011, 0]])
        for extra, reason in [({'class': 'footway'}, 'unsupported_road_role'),
                ({'level_rules': [{'value': 0}]}, 'unsupported_level_rules'),
                ({'level_rules': [{'value': 1, 'between': [.1, .9]}]}, 'unsupported_level_rules'),
                ({'connectors': []}, 'missing_endpoint_identity')]:
            (nodes, issues, _), _ = self.fragments([{**base, **extra}])
            self.assertEqual(nodes, {}); self.assertIn(reason, issues[0]['reasons'])

    def test_access_scopes_and_speed_parser_are_preserved(self):
        row = connected('a', [[-.001, 0], [.011, 0]], access_restrictions=[{'access_type': 'allowed', 'when': {'heading': 'forward'}}],
            speed_limits=[{'max_speed': {'value': 35, 'unit': 'mph'}}])
        (nodes, _, _), meta = self.fragments([row])
        self.assertTrue(self.search(nodes)['candidates'])
        self.assertEqual(meta[0]['frozenLimit']['status'], 'access_scoped_or_restricted')
        self.assertAlmostEqual(meta[0]['frozenSpeedOnlyLimit']['kmh'], 56.32704)

    def test_window_checks_include_interior_vertices_and_exact_boundary(self):
        line = [[0, 0], [.005, .01], [.01, 0]]; lengths = cumulative_lengths(line)
        self.assertFalse(interval_in_window(line, lengths, .1, .9, [0, -.001, .01, .005]))
        self.assertTrue(interval_in_window([[0, 0], [.01, 0]], cumulative_lengths([[0, 0], [.01, 0]]), 0, 1, [0, 0, .01, .01]))
        (nodes, issues, _), _ = self.fragments([connected('a', [[-.001, 0], [.011, 0]])], box=[0, -.001, .005, .001])
        self.assertEqual(nodes, {}); self.assertIn('outside_window_fragment', str(issues))

    def test_original_weights_define_partial_support(self):
        row = connected('a', [[-.001, 0], [.001, 0]])
        (nodes, _, _), _ = self.fragments([row], [[0] if i < 5 else [] for i in range(50)])
        self.assertFalse(self.search(nodes)['candidates'])
        self.assertTrue(self.search(nodes, [100.] * 5 + [1.] * 45)['candidates'])

    def test_saved_full_nodes_stay_exact_even_with_new_variants(self):
        (nodes, _, _), _ = self.fragments([connected('a', [[0, 0], [.01, 0]])])
        full = nodes['0/full']
        self.assertEqual(full['entryId'], 'a'); self.assertEqual(full['exitId'], 'b')
        self.assertEqual(full['entryFraction'], 0.); self.assertEqual(full['exitFraction'], 1.)
        self.assertTrue(any(not c['hasTerminalCut'] for c in self.search(nodes)['candidates']))

    def test_caps_retain_partial_candidates_and_empty_is_unmeasured(self):
        def full(i, bits):
            n = node(i, str(i), str(i + 1), bits)
            return {**n, 'mode': 'full', 'variantKey': f'{i}/full'}
        nodes = {f'{i}/full': full(i, range(50)) for i in range(2)}
        result = self.search(nodes, maximum_states=1)
        self.assertEqual(len(result['candidates']), 1); self.assertTrue(result['searchCapped'])
        self.assertEqual(fragment_status(result, 2), 'search_capped')
        chain = {f'{i}/full': full(i, [i, i + 1]) for i in range(65)}
        self.assertIn('chain_length', self.search(chain, [1.] * 100)['capReasons'])
        self.assertFalse(self.search({'0/full': full(0, [0, 1])}, maximum_rows=1)['searchCapped'])
        self.assertEqual(fragment_status(self.search({}), 0), 'unmeasured_empty_cache')
        with self.assertRaises(PilotError): search_fragments({}, [0.])

    def test_minimal_paths_and_no_repeated_source_row(self):
        def variant(key, ordinal, enter, exit_, bits, mode='full'):
            return {**node(ordinal, enter, exit_, bits), 'variantKey': key, 'mode': mode}
        nodes = {'a': variant('a', 0, 'x', 'join', [0, 1]), 'b': variant('b', 1, 'join', 'z', range(1, 50))}
        self.assertEqual([c['rowOrdinals'] for c in self.search(nodes)['candidates']], [[1]])
        self.assertFalse(self.search({'b': nodes['b']}, maximum_states=1)['searchCapped'])
        repeated = {'a': variant('a', 0, None, 'j1', [0, 1], 'start'),
            'b': variant('b', 1, 'j1', 'j2', [2, 3]), 'c': variant('c', 0, 'j2', None, [4, 5], 'end')}
        self.assertEqual(self.search(repeated, [1.] * 6)['candidates'], [])

    def fixture(self):
        inputs = self.root / 'inputs'; inputs.mkdir()
        paths = {k: inputs / (k + '.json') for k in ['segments', 'scopes', 'matches', 'support', 'proposal', 'compatibilityReport', 'previousReport']}
        rows = [connected('a', [[-.001, 0], [.005, 0]], 'start', 'join'), connected('b', [[.005, 0], [.011, 0]], 'join', 'end')]
        prepared = []
        with paths['segments'].open('wb') as source, paths['scopes'].open('w') as scopes:
            for ordinal, row in enumerate(rows):
                raw = (json.dumps(row) + '\n').encode(); source.write(raw)
                saved, slim = prepare_row(row, self.windows); slim['_ordinal'] = ordinal; prepared.append(slim)
                scope = {'ordinal': ordinal, 'id': row['id'], 'version': row['version'], 'frozenLimit': saved['limit'],
                    'frozenSpeedOnlyLimit': saved['speedOnlyLimit'], 'fieldsSha256': saved['fieldsSha256'],
                    'rawLineSha256': hashlib.sha256(raw).hexdigest(), 'memberships': saved['memberships'],
                    'rawSpeedLimits': None, 'rawAccessRestrictions': None}
                scopes.write(json.dumps(scope) + '\n')
        sample_count = 0
        with paths['matches'].open('wb') as matches, paths['support'].open('w') as supports:
            for window, spans, speed in [(self.windows[0], [([0, 0], [.01, 0], 99.)], 105),
                                         (self.windows[1], [([1, 1], [1.01, 1], 13.)], 85)]:
                index = MatchIndex(prepared, window['bbox'])
                saved = cache_match(index, spans); saved.update(windowId=window['id'], arc=0, sourceClassKph=speed, sourceSpans=spans)
                raw = (json.dumps(saved) + '\n').encode(); matches.write(raw)
                old_support = support(index, spans); old_support.update(windowId=window['id'], arc=0, savedMatchLineSha256=hashlib.sha256(raw).hexdigest())
                supports.write(json.dumps(old_support) + '\n'); sample_count += len(old_support['samples'])
        paths['proposal'].write_text(json.dumps({'selection': {'windows': self.windows}}))
        prior = {'frozenLimitStatusCounts': {'missing': 2}, 'scopeCounts': {'speed': {'presentRows': 0}, 'access': {'presentRows': 0}},
            'publisherGeometryKm': {'a': 0, 'empty': 0}, 'windows': [{'id': 'a', 'cachedRows': 2}, {'id': 'empty', 'cachedRows': 0}]}
        paths['compatibilityReport'].write_text(json.dumps(prior))
        plan = {'expectedRows': 2, 'expectedMatches': 2, 'expectedSamples': sample_count, 'expectedWindows': 2,
            'maxLineBytes': 4194304, 'maximumRowsPerChain': 64, 'maximumExpandedStatesPerArc': 4096}
        old_root = self.root / 'old'; old_root.mkdir()
        with contextlib.redirect_stdout(io.StringIO()): old_analyze(plan, Output(old_root, 4 * 1024 ** 2, 5), paths)
        paths['chains'] = old_root / 'chains.jsonl'; original = json.loads(paths['chains'].read_text().splitlines()[0])
        self.assertEqual(original['candidates'], [])
        paths['previousReport'].write_text(json.dumps({**prior, 'cohorts': {'all': {'originalCandidateChains': 0}}}))
        out_root = self.root / 'new'; out_root.mkdir()
        return plan, paths, Output(out_root, 4 * 1024 ** 2, 5)

    def test_pipeline_without_old_matcher_replay_and_audit_rejects_tampering(self):
        plan, paths, output = self.fixture(); original_bytes = paths['chains'].read_bytes()
        with patch('coarse_timing_chains.make_nodes', side_effect=AssertionError('old producer replay')), patch('coarse_timing_chains.search_chains', side_effect=AssertionError('old producer replay')):
            analyze(plan, output, paths); audit(plan, output, paths)
        report = json.loads((output.root / 'report.json').read_text())
        self.assertTrue(report['hypothesisSupported']); self.assertEqual(report['allWindows']['newUncappedClippedRecords'], 1)
        self.assertEqual(report['allWindows']['arcCount'], 2); self.assertEqual(report['allWindows']['sourceKm'], 112.)
        self.assertEqual(report['windows'][1]['totals']['statusCounts'], {'unmeasured_empty_cache': 1})
        self.assertEqual(paths['chains'].read_bytes(), original_bytes)
        result_path = output.root / 'fragments.jsonl'; all_records = [json.loads(line) for line in result_path.read_text().splitlines()]
        original = all_records[0]
        self.assertEqual(original['original'], json.loads(original_bytes.splitlines()[0]))
        def mutate_fraction(r): r['nodes'][0]['entryFraction'] += .1
        def mutate_projection(r): r['projections'][0]['projections'][0]['fraction'] += .1
        def mutate_weight(r): r['candidates'][0]['supportedKm'] += 1
        def mutate_original(r): r['original']['status'] = 'promoted'
        def mutate_claim(r): r['carAccessVerified'] = True
        for mutate in [mutate_fraction, mutate_projection, mutate_weight, mutate_original, mutate_claim]:
            with self.subTest(mutate=mutate.__name__):
                changed = deepcopy(original); mutate(changed); result_path.write_text(''.join(json.dumps(r) + '\n' for r in [changed, *all_records[1:]]))
                with self.assertRaises(PilotError): audit(plan, output, paths)


if __name__ == '__main__':
    unittest.main()
