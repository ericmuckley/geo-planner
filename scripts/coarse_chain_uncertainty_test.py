"""Reporting-scope preservation and uncertainty checks; no real matcher replay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analyze_chain_exclusions import analyze as seed_exclusions
from analyze_timing_cache import Output, prepare_row
from classify_chain_uncertainty import analyze, classify, samples_preserved, summarize
from coarse_chain_exclusions_test import fixture as seed_fixture
from coarse_chain_uncertainty_audit import audit, reference_scope, reference_summary
from coarse_timing_chains import row_metadata
from coarse_timing_input import PilotError


def chain(reasons=None, candidates=1, capped=False, original_exhaustive=False, status='unresolved_with_candidates'):
    return {'excludedRows': [{'ordinal': i, 'reasons': values} for i, values in enumerate(reasons or [])],
        'candidates': [{'rowOrdinals': [i, i + 10]} for i in range(candidates)], 'searchCapped': capped,
        'searchExhaustiveForDeclaredRows': original_exhaustive, 'status': status}


def fixture(root, out_of_role):
    plan, paths = seed_fixture(root)
    source = [json.loads(v) for v in paths['segments'].read_text().splitlines()]
    scopes = [json.loads(v) for v in paths['scopes'].read_text().splitlines()]
    windows = json.loads(paths['proposal'].read_text())['selection']['windows']
    if out_of_role:
        source[2]['class'] = 'footway'
    metadata = []
    with paths['segments'].open('wb') as stream, paths['scopes'].open('w') as scope_file, paths['rows'].open('w') as rows:
        for i, row in enumerate(source):
            raw = (json.dumps(row) + '\n').encode(); stream.write(raw)
            prepared, _ = prepare_row(row, windows)
            scopes[i].update(frozenLimit=prepared['limit'], frozenSpeedOnlyLimit=prepared['speedOnlyLimit'],
                fieldsSha256=prepared['fieldsSha256'], rawLineSha256=hashlib.sha256(raw).hexdigest())
            scope_file.write(json.dumps(scopes[i]) + '\n')
            meta = row_metadata(row, scopes[i]); rows.write(json.dumps(meta) + '\n'); metadata.append(meta)
    original = [json.loads(v) for v in paths['chains'].read_text().splitlines()]
    for r in original:
        r['searchExhaustiveForDeclaredRows'] = False
        for e in r['excludedRows']: e['reasons'] = metadata[e['ordinal']]['baseReasons']
    paths['chains'].write_text(''.join(json.dumps(r) + '\n' for r in original))
    previous = json.loads(paths['previousReport'].read_text())
    previous['frozenLimitStatusCounts'] = {'missing': 2, 'unsupported_road_role': 1} if out_of_role else {'missing': 3}
    paths['previousReport'].write_text(json.dumps(previous))
    seed_root = root / 'seed-exclusion'; seed_root.mkdir()
    seed_exclusions(plan, Output(seed_root, 2 * 1024 ** 2, 5), paths)
    paths['previousReport'] = seed_root / 'report.json'
    paths['levels'] = seed_root / 'levels.jsonl'
    paths['exclusions'] = seed_root / 'exclusions.jsonl'
    return plan, paths, original


class UncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def check_reference(self, original, cached):
        result = classify(original, cached)
        for key, value in reference_scope(original, cached).items(): self.assertEqual(result[key], value)
        return result

    def test_out_of_role_row_retains_all_additional_reasons(self):
        original = chain([['unsupported_road_role', 'unsupported_level_rules', 'outside_window_endpoint']])
        before = deepcopy(original)
        result = self.check_reference(original, 1)
        self.assertEqual(result['status'], 'single_declared_role_chain')
        self.assertTrue(result['newlyExhaustiveCandidateRecord'])
        self.assertEqual(result['declaredOutOfRoleRows'], original['excludedRows'])
        self.assertEqual(original, before)
        for field in ['sourceComplete', 'physicalIdentityVerified', 'carAccessVerified']: self.assertFalse(result[field])

    def test_in_role_levels_ids_distance_and_ties_remain_blockers(self):
        for reason in ['unsupported_level_rules', 'missing_endpoint_identity', 'malformed_connector',
                       'outside_window_endpoint', 'endpoint_not_near_own_samples', 'nonprogressing_or_tied_endpoints', 'unknown_future_reason']:
            with self.subTest(reason=reason):
                result = self.check_reference(chain([[reason]]), 1)
                self.assertEqual(result['status'], 'unresolved_in_role_with_candidates')
                self.assertFalse(result['exhaustiveWithinDeclaredRoleScope'])

    def test_mixed_role_partition_does_not_hide_an_in_role_row(self):
        result = self.check_reference(chain([['unsupported_road_role'], ['unsupported_level_rules']]), 2)
        self.assertEqual(len(result['declaredOutOfRoleRows']), 1)
        self.assertEqual(len(result['unresolvedInRoleRows']), 1)
        self.assertFalse(result['newlyExhaustiveCandidateRecord'])

    def test_cap_prevents_exhaustiveness_with_partial_candidates(self):
        original = chain([['unsupported_road_role']], candidates=2, capped=True)
        result = self.check_reference(original, 2)
        self.assertEqual(result['status'], 'search_capped')
        self.assertEqual(result['savedCandidateCount'], 2)
        self.assertFalse(result['exhaustiveWithinDeclaredRoleScope'])

    def test_empty_cache_stays_unmeasured(self):
        result = self.check_reference(chain(candidates=0), 0)
        self.assertEqual(result['status'], 'unmeasured_empty_cache')
        self.assertFalse(result['exhaustiveWithinDeclaredRoleScope'])

    def test_zero_single_and_multiple_saved_candidates_are_distinct(self):
        for n, label in [(0, 'no_declared_role_chain'), (1, 'single_declared_role_chain'), (2, 'multiple_declared_role_chains')]:
            original = chain([['unsupported_road_role']], candidates=n)
            before = deepcopy(original)
            result = self.check_reference(original, 1)
            self.assertEqual(result['status'], label)
            self.assertEqual(original, before)

    def test_already_exhaustive_result_is_not_a_new_hypothesis_positive(self):
        result = self.check_reference(chain(original_exhaustive=True, status='single_cached_chain'), 1)
        self.assertTrue(result['exhaustiveWithinDeclaredRoleScope'])
        self.assertFalse(result['newlyExhaustiveCandidateRecord'])

    def test_duplicate_excluded_ids_or_invalid_flags_fail(self):
        original = chain([['unsupported_road_role'], ['unsupported_level_rules']])
        original['excludedRows'][1]['ordinal'] = 0
        with self.assertRaises(PilotError): classify(original, 1)
        with self.assertRaises(PilotError): classify(chain(), -1)
        with self.assertRaises(PilotError): classify({**chain(), 'searchCapped': 'false'}, 1)

    def test_saved_nonuniform_weights_are_accounted_without_geometry(self):
        match = {'sourceSpans': [([0, 0], [1, 0], 90.), ([1, 0], [2, 0], 9.)], 'sourceKm': 99.}
        saved = {'samples': [[0, 0, 2, 45., []], [0, 1, 2, 45., []], [1, 0, 1, 9., []]]}
        self.assertEqual(samples_preserved(match, saved), 3)
        saved['samples'][0][3] = 44.
        with self.assertRaises(PilotError): samples_preserved(match, saved)

    def test_end_to_end_preserves_every_original_field_and_audit_rejects_permission_claim(self):
        plan, paths, original = fixture(self.root, out_of_role=True)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        analyze(plan, output, paths); audit(plan, output, paths)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertTrue(report['reportingHypothesisSupported'])
        records = [json.loads(v) for v in (self.root / 'role-scope.jsonl').read_text().splitlines()]
        for old, new in zip(original, records):
            self.assertEqual({k: v for k, v in new.items() if k not in ['declaredRoleScope', 'reportingProvenance']}, old)
        self.assertEqual(summarize(records), reference_summary(records))
        self.assertEqual(report['completedSourceWindows'], 0)
        self.assertFalse(report['originalFeasibilityQualified'])
        records[0]['declaredRoleScope']['physicalIdentityVerified'] = True
        (self.root / 'role-scope.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
        with self.assertRaises(PilotError): audit(plan, output, paths)

    def test_nonempty_level_rule_stays_unresolved_even_when_raw_value_is_zero(self):
        plan, paths, _ = fixture(self.root, out_of_role=False)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        analyze(plan, output, paths); audit(plan, output, paths)
        report = json.loads((self.root / 'report.json').read_text())
        self.assertFalse(report['reportingHypothesisSupported'])
        self.assertEqual(report['cohorts']['candidate_bearing']['roleScopedStatusCounts'], {'unresolved_in_role_with_candidates': 1})

    def test_no_geometry_or_matcher_is_replayed(self):
        plan, paths, _ = fixture(self.root, out_of_role=True)
        output = Output(self.root, 2 * 1024 ** 2, 5)
        forbidden = AssertionError('Geometry/matcher replay is forbidden')
        with patch('coarse_timing_chains.search_chains', side_effect=forbidden), patch('coarse_timing_chains.make_nodes', side_effect=forbidden), patch('coarse_timing_chains.sample_points', side_effect=forbidden), patch('coarse_timing_chains.adjacency', side_effect=forbidden):
            analyze(plan, output, paths); audit(plan, output, paths)


if __name__ == '__main__':
    unittest.main()
