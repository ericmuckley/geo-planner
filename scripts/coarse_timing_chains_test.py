"""Synthetic chain, ambiguity, progress, cap and independent-audit cases."""
import contextlib
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import struct
import unittest

from analyze_timing_cache import Output, cache_match, prepare_row
from analyze_timing_compatibility import support
from coarse_timing_cache_test import road
from coarse_timing_chains import analyze, can_join, make_nodes, outcome, row_metadata, sample_points, search_chains
from coarse_timing_chains_audit import audit, reference_search
from coarse_timing_input import PilotError
from coarse_timing_parquet import MatchIndex


def connected(identity, first, last, enter, exit_, **extra):
    return road(identity, [first, last], connectors=[{'at': 0., 'connector_id': enter}, {'at': 1., 'connector_id': exit_}], **extra)


def node(i, enter, exit_, bits, first=None, last=None):
    low, high = min(bits), max(bits)
    return {'ordinal': i, 'direction': 0, 'entryId': enter, 'exitId': exit_,
        'entryPoint': first or [0, 0], 'exitPoint': last or [0, 0],
        'entryProgress': [low, low], 'exitProgress': [high, high],
        'sampleMin': low, 'sampleMax': high, 'maskHex': hex(sum(1 << b for b in bits))}


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.box = [-.01, -.01, .02, .01]
        self.windows = [{'id': 'a', 'bbox': self.box}, {'id': 'empty', 'bbox': [1, 1, 2, 2]}]

    def metadata(self, row, ordinal=0):
        saved, _ = prepare_row(row, self.windows)
        scope = {'ordinal': ordinal, 'frozenLimit': saved['limit'], 'frozenSpeedOnlyLimit': saved['speedOnlyLimit'],
                 'rawLineSha256': 'fixture', 'fieldsSha256': saved['fieldsSha256'], 'memberships': saved['memberships']}
        return row_metadata(row, scope)

    def test_connected_split_rows_qualify_at_original_weights(self):
        nodes = {0: node(0, 'a', 'b', range(0, 5)), 1: node(1, 'b', 'c', range(5, 10))}
        result = search_chains(nodes, [9.9] * 10)
        self.assertEqual([c['rowOrdinals'] for c in result['candidates']], [[0, 1]])
        self.assertAlmostEqual(result['candidates'][0]['supportedKm'], 99)
        self.assertFalse(result['searchCapped'])
        self.assertEqual(result, reference_search(nodes, [9.9] * 10, 64, 4096))

    def test_geometric_union_without_shared_id_cannot_join(self):
        nodes = {0: node(0, 'a', 'b', range(5)), 1: node(1, 'different', 'c', range(5, 10))}
        self.assertEqual(search_chains(nodes, [1.] * 10)['candidates'], [])

    def test_shared_id_with_coordinate_gap_cannot_join(self):
        a, b = node(0, 'a', 'b', range(5)), node(1, 'b', 'c', range(5, 10), first=[.01, 0])
        self.assertFalse(can_join(a, b))

    def test_two_branches_remain_multiple_candidates(self):
        nodes = {0: node(0, 'a', 'b', range(5)), 1: node(1, 'b', 'c', range(5, 10)),
                 2: node(2, 'b', 'd', range(5, 10))}
        result = search_chains(nodes, [1.] * 10)
        self.assertEqual(len(result['candidates']), 2)
        self.assertEqual(outcome(result, [], 3), 'multiple_cached_chains')

    def test_nonprogressing_join_is_rejected(self):
        a, b = node(0, 'a', 'b', range(5, 10)), node(1, 'b', 'c', range(5))
        self.assertFalse(can_join(a, b))

    def test_minimality_removes_redundant_leading_segment(self):
        nodes = {0: node(0, 'a', 'b', [0, 1]), 1: node(1, 'b', 'c', range(1, 10))}
        result = search_chains(nodes, [1.] * 10)
        self.assertEqual([c['rowOrdinals'] for c in result['candidates']], [[1]])
        self.assertEqual(result, reference_search(nodes, [1.] * 10, 64, 4096))

    def test_original_weights_not_sample_count_define_threshold(self):
        nodes = {0: node(0, 'a', 'b', [0, 1])}
        result = search_chains(nodes, [45., 45.] + [1.] * 8)
        self.assertEqual(len(result['candidates']), 1)
        self.assertAlmostEqual(result['candidates'][0]['supportedKm'], 90)

    def test_state_cap_retains_partial_candidates_without_uniqueness_claim(self):
        nodes = {0: node(0, 'a', 'b', range(10)), 1: node(1, 'c', 'd', range(10))}
        result = search_chains(nodes, [1.] * 10, maximum_states=1)
        self.assertEqual(len(result['candidates']), 1)
        self.assertTrue(result['searchCapped'])
        self.assertEqual(outcome(result, [], 2), 'search_capped')
        self.assertEqual(result, reference_search(nodes, [1.] * 10, 64, 1))

    def test_length_cap_and_terminal_length_are_distinct(self):
        nodes = {i: node(i, str(i), str(i + 1), range(i * 2, i * 2 + 2)) for i in range(5)}
        result = search_chains(nodes, [1.] * 10, maximum_rows=2)
        self.assertIn('chain_length', result['capReasons'])
        self.assertEqual(result, reference_search(nodes, [1.] * 10, 2, 4096))
        terminal = search_chains({0: node(0, 'a', 'b', [0, 1])}, [1.] * 10, maximum_rows=1)
        self.assertFalse(terminal['searchCapped'])

    def test_frozen_sixty_four_row_limit_is_enforced(self):
        nodes = {i: node(i, str(i), str(i + 1), [i, i + 1]) for i in range(65)}
        result = search_chains(nodes, [1.] * 100)
        self.assertIn('chain_length', result['capReasons'])
        self.assertLessEqual(result['expandedStates'], 4096)
        self.assertEqual(result['candidates'], [])

    def test_unknown_metadata_keeps_explicit_reasons(self):
        base = connected('a', [0, 0], [.01, 0], 'x', 'y')
        self.assertIn('unsupported_level_rules', self.metadata({**base, 'level_rules': [{'value': 0}]})['baseReasons'])
        self.assertIn('unsupported_road_role', self.metadata({**base, 'class': 'footway'})['baseReasons'])
        self.assertIn('missing_endpoint_identity', self.metadata({**base, 'connectors': [{'at': .5, 'connector_id': 'x'}]})['baseReasons'])
        multiple = {**base, 'connectors': base['connectors'] + [{'at': 0., 'connector_id': 'other'}]}
        self.assertIn('multiple_endpoint_identities', self.metadata(multiple)['baseReasons'])

    def test_multipart_geometry_and_malformed_connectors_stay_unresolved(self):
        first = base64.b64decode(road('a', [[0, 0], [.002, 0]])['geometryWkbBase64'])
        second = base64.b64decode(road('b', [[.008, 0], [.01, 0]])['geometryWkbBase64'])
        row = connected('a', [0, 0], [.01, 0], 'x', 'y')
        row['geometryWkbBase64'] = base64.b64encode(struct.pack('<BII', 1, 5, 2) + first + second).decode()
        self.assertIn('multipart_geometry', self.metadata(row)['baseReasons'])
        row = connected('a', [0, 0], [.01, 0], 'x', 'y')
        row['connectors'].append({'at': True, 'connector_id': 'bad'})
        self.assertIn('malformed_connector', self.metadata(row)['baseReasons'])

    def test_reversed_raw_geometry_has_forward_sample_progress(self):
        row = connected('a', [.01, 0], [0, 0], 'exit', 'entry')
        metadata = [self.metadata(row)]
        points = [[(.5 + i) * .0002, 0] for i in range(50)]
        samples = [[0, i, 50, 1., [0]] for i in range(50)]
        nodes, excluded = make_nodes(metadata, samples, points, self.box)
        self.assertEqual(excluded, [])
        self.assertEqual(nodes[0]['direction'], 1)
        self.assertEqual(nodes[0]['entryId'], 'entry')
        self.assertEqual(nodes[0]['exitId'], 'exit')

    def test_outside_endpoint_and_progress_ties_are_unresolved(self):
        metadata = [self.metadata(connected('a', [.00499, 0], [.00501, 0], 'x', 'y'))]
        nodes, excluded = make_nodes(metadata, [[0, 0, 1, 1., [0]]], [[.005, 0]], self.box)
        self.assertEqual(nodes, {})
        self.assertIn('nonprogressing_or_tied_endpoints', excluded[0]['reasons'])
        metadata = [self.metadata(connected('a', [0, 0], [.01, 0], 'x', 'y'))]
        nodes, excluded = make_nodes(metadata, [[0, 0, 1, 1., [0]]], [[0, 0]], [-.001, -.001, .005, .001])
        self.assertIn('outside_window_endpoint', excluded[0]['reasons'])
        self.assertEqual(outcome({'searchCapped': False, 'candidates': []}, excluded, 1), 'unresolved_without_candidates')

    def test_raw_scoped_limits_are_not_averaged_or_granted_access(self):
        row = connected('a', [0, 0], [.01, 0], 'x', 'y', speed_limits=[{'max_speed': {'value': 35, 'unit': 'mph'}}],
            access_restrictions=[{'access_type': 'allowed', 'when': {'heading': 'forward'}}])
        result = self.metadata(row)
        self.assertEqual(result['frozenLimit']['status'], 'access_scoped_or_restricted')
        self.assertAlmostEqual(result['frozenSpeedOnlyLimit']['kmh'], 56.32704)
        self.assertIn('scopeRulesSha256', result)

    def test_empty_cache_has_no_exhaustive_absence_claim(self):
        self.assertEqual(outcome(search_chains({}, [1.]), [], 0), 'unmeasured_empty_cache')
        with self.assertRaises(PilotError): search_chains({}, [0.])

    def test_end_to_end_preserves_denominators_and_audit_detects_tampered_chain(self):
        inputs = self.root / 'inputs'; inputs.mkdir()
        paths = {k: inputs / (k + '.json') for k in ['segments', 'scopes', 'matches', 'support', 'proposal', 'compatibilityReport']}
        rows = [connected('a', [0, 0], [.005, 0], 'start', 'join'), connected('b', [.005, 0], [.01, 0], 'join', 'end')]
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
        index, spans = MatchIndex(prepared, self.box), [([0, 0], [.01, 0], 99.)]
        old = cache_match(index, spans); old.update(windowId='a', arc=0, sourceClassKph=105, sourceSpans=spans)
        raw = (json.dumps(old) + '\n').encode(); paths['matches'].write_bytes(raw)
        previous = support(index, spans); previous.update(windowId='a', arc=0, savedMatchLineSha256=hashlib.sha256(raw).hexdigest())
        paths['support'].write_text(json.dumps(previous) + '\n')
        paths['proposal'].write_text(json.dumps({'selection': {'windows': self.windows}}))
        paths['compatibilityReport'].write_text(json.dumps({'frozenLimitStatusCounts': {'missing': 2},
            'scopeCounts': {'speed': {'presentRows': 0}, 'access': {'presentRows': 0}}, 'publisherGeometryKm': {'a': 0, 'empty': 0},
            'windows': [{'id': 'a', 'cachedRows': 2}, {'id': 'empty', 'cachedRows': 0}]}))
        plan = {'expectedRows': 2, 'expectedMatches': 1, 'expectedSamples': len(previous['samples']), 'expectedWindows': 2,
                'maxLineBytes': 4194304, 'maximumRowsPerChain': 64, 'maximumExpandedStatesPerArc': 4096}
        output = Output(self.root, 1024 ** 2, 5)
        with contextlib.redirect_stdout(io.StringIO()): analyze(plan, output, paths)
        audit(plan, output, paths)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertTrue(report['hypothesisSupported'])
        self.assertEqual(report['allWindows']['arcCount'], 1)
        self.assertEqual(len(report['windows']), 2)
        self.assertFalse(report['originalFeasibilityQualified'])
        chain_path = self.root / 'chains.jsonl'; chain = json.loads(chain_path.read_text())
        chain['candidates'][0]['rowOrdinals'] = [0, 0]
        chain_path.write_text(json.dumps(chain) + '\n')
        with self.assertRaises(PilotError): audit(plan, output, paths)


if __name__ == '__main__':
    unittest.main()
