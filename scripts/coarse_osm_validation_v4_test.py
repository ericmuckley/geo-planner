"""Reference-equivalence and independent-closure controls for the validator prototype."""
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_bulk_audit  # Keep the independent audit bound to the reference validator.
from coarse_osm_bulk import Run, checked_records as reference, extract
from coarse_osm_bulk_test import objects, STATE, PROPOSAL
from coarse_osm_records import canonical, utc as reference_utc
from coarse_osm_validation_v4 import checked_records, utc
from coarse_timing_input import PilotError


def proposal():
    value = json.loads(PROPOSAL.read_text())
    value['proposedCaps'].update(sqliteIndexBytesEach=1048576, sqliteMaxPagesEach=256, sqliteCacheBytesEach=8192,
        workingBytesIncludingTmp=33554432, tmpBytes=65536, pythonSelectionStateBytes=4194304, retainedNativeObjectBytes=1048576,
        normalizedExtractBytes=1048576, scanNodesPerPass=10000, scanWaysPerPass=100, scanRelationsPerPass=100, scanObjectVisitsTotal=50000)
    value['windows'] = [{'id': 'a', 'bbox': [0, 0, 1, 1]}, {'id': 'b', 'bbox': [.25, .25, .75, .75]}]
    return value


class Tests(unittest.TestCase):
    def compare(self, rows, config=None):
        results = []
        for implementation in (reference, checked_records):
            with tempfile.TemporaryDirectory() as folder:
                run = Run(folder, config or proposal())
                output = []
                try:
                    for row in implementation(lambda: iter(deepcopy(rows)), run, STATE, 'test'):
                        output.append(canonical(row))
                    accepted = True
                except (PilotError, ValueError, TypeError, OverflowError):
                    accepted = False
                results.append((accepted, output, run.state['scanObjectVisits'], run.state['passes']))
        self.assertEqual(*results)
        return results[0][0]

    def test_utc_acceptance_and_values_match_reference(self):
        values = ['0001-01-01T00:00:00Z', '2000-02-29T23:59:59Z', STATE, '9999-12-31T23:59:59Z',
            '2026-02-29T00:00:00Z', '2026-01-01T24:00:00Z', '2026-01-01T00:60:00Z',
            '2026-01-01T00:00:60Z', '2026-1-01T00:00:00Z', '2026-01-01T00:00:00+00:00',
            '2026-01-01T00:00:00.0Z', '2026-01-01T00:00:00Z\n', None, 1, [], {}, True]
        values += [STATE.translate(str.maketrans('0123456789', alphabet)) for alphabet in ['٠١٢٣٤٥٦٧٨٩', '０１２３４５６７８９']]
        for value in values:
            outcomes = []
            for implementation in (reference_utc, utc):
                try:
                    outcomes.append(('valid', implementation(value)))
                except (PilotError, ValueError, TypeError):
                    outcomes.append(('invalid',))
            with self.subTest(value=value):
                self.assertEqual(*outcomes)

    def test_valid_typed_records_are_unchanged(self):
        self.assertTrue(self.compare(objects()))
        rows = objects()
        rows[0]['visible'] = True
        rows[0]['tags'] = {'unicode': 'ø 😀', 'quote': 'a"\\b'}
        self.assertTrue(self.compare(rows))

    def test_invalid_record_and_stream_controls_match_reference(self):
        variants = [None, [], {'type': 'unknown'}]
        for key, values in {'id': [0, -1, True, '1'], 'version': [0, None, True],
            'timestamp': ['2030-01-01T00:00:00Z', '2026-02-29T00:00:00Z', None],
            'visible': [False, None, 1], 'lat': [91., True, None, float('nan')],
            'lon': [-181., '0', float('inf')], 'tags': [None, [], {'a': 1}]}.items():
            for value in values:
                row = deepcopy(objects()[0]); row[key] = value; variants.append(row)
        for row in variants:
            with self.subTest(row=row):
                self.assertFalse(self.compare([row]))
        for index, key, value in [(4, 'nodes', [1]), (4, 'nodes', [True, 2]), (7, 'members', None),
            (7, 'members', [{'type': 'way', 'ref': 0, 'role': ''}])]:
            rows = objects(); rows[index][key] = value; self.assertFalse(self.compare(rows))
        rows = objects(); rows.insert(1, deepcopy(rows[0])); self.assertFalse(self.compare(rows))
        rows = objects(); rows[0], rows[1] = rows[1], rows[0]; self.assertFalse(self.compare(rows))

    def test_seeded_node_boundary_corpus_matches_reference(self):
        rng = random.Random(2701)
        for _ in range(80):
            row = deepcopy(objects()[0]); row['lat'] = rng.choice([-90, 90, -90.001, 90.001, rng.uniform(-90, 90)])
            row['lon'] = rng.choice([-180, 180, -180.001, 180.001, rng.uniform(-180, 180)])
            self.compare([row])

    def test_row_visit_record_and_wall_caps_match_reference(self):
        for key, value in [('scanNodesPerPass', 1), ('scanObjectVisitsTotal', 2), ('singleNormalizedElementBytes', 10), ('wallSeconds', 0)]:
            config = proposal(); config['proposedCaps'][key] = value
            self.assertFalse(self.compare(objects(), config))

    def test_checkpoint_cadence_and_eof_match_reference(self):
        rows = [dict(objects()[0], id=i) for i in range(1, 258)]
        for implementation in (reference, checked_records):
            with tempfile.TemporaryDirectory() as folder:
                run = Run(folder, proposal())
                with patch.object(run, 'checkpoint', wraps=run.checkpoint) as checkpoints:
                    self.assertEqual(len(list(implementation(lambda: iter(rows), run, STATE, 'test'))), 257)
                self.assertEqual(checkpoints.call_count, 4)
                self.assertEqual(run.state['passes'][0]['status'], 'eof')

    def test_full_primary_integration_keeps_independent_audit_and_closure(self):
        results = []
        self.assertIs(coarse_osm_bulk_audit.checked_records, reference)
        for implementation in (reference, checked_records):
            with tempfile.TemporaryDirectory() as folder:
                with patch('coarse_osm_bulk.checked_records', implementation):
                    state = extract(lambda: iter(deepcopy(objects())), proposal(), folder,
                        source_identity={'publisherStateUtc': STATE, 'kind': 'synthetic'})
                self.assertEqual(state['status'], 'extracted_publisher_file_analysis_pending')
                self.assertEqual(state['scanObjectVisits'], 36)
                self.assertFalse(state['sourceFeasibilityQualified'])
                results.append((Path(folder, 'elements.jsonl').read_bytes(), json.loads(Path(folder, 'audit.json').read_text())))
        self.assertEqual(*results)
        rows = [json.loads(line) for line in results[0][0].splitlines()]
        self.assertEqual({(r['element']['type'], r['element']['id']) for r in rows}, {('node', 1), ('node', 2), ('way', 1), ('relation', 1)})
        self.assertEqual(next(r['element']['members'][-1]['ref'] for r in rows if r['element']['type'] == 'relation'), 999)


if __name__ == '__main__':
    unittest.main()
