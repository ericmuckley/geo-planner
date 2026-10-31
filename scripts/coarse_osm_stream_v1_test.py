"""Exact compact storage and adversarial two-pass controls; no road acquisition."""
from copy import deepcopy
import datetime
import hashlib
import json
from pathlib import Path
import random
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coarse_osm_bulk import Run, checked_records as reference_checked, extract as reference_extract, records as reference_records
from coarse_osm_bulk_pbf import native_records
from coarse_osm_compact_v1 import Index, Storage, coordinate
from coarse_osm_native_smoke import STATE, fixture_records, write_xml
from coarse_osm_inventory import project as reference_project
from coarse_osm_stream_v1 import NativeValidator, extract, native_scan
from coarse_timing_input import PilotError

try:
    import osmium
except ImportError:
    osmium = None

REPO = Path(__file__).resolve().parents[1]


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.serial = 0
        self.config = json.loads((REPO / 'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json').read_text())
        self.config['windows'] = [{'id': 'a', 'bbox': [0, 0, 1, 1]}, {'id': 'b', 'bbox': [.25, .25, .75, .75]}]
        self.config['source']['proposedPublisherReplicationStateUtc'] = STATE
        self.config['proposedCaps'].update(sqliteIndexBytesEach=1048576, sqliteMaxPagesEach=256, sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432, tmpBytes=65536, pythonSelectionStateBytes=4194304,
            retainedNativeObjectBytes=1048576, normalizedExtractBytes=1048576,
            scanNodesPerPass=100, scanWaysPerPass=100, scanRelationsPerPass=100, scanObjectVisitsTotal=1200, wallSeconds=30)

    def directory(self):
        self.serial += 1
        path = self.root / str(self.serial)
        path.mkdir()
        return path

    def index(self, **kwargs):
        return Index(self.directory() / 'index', Storage(33554432, 1048576), rows_per_shard=2, **kwargs)

    def run_extract(self, rows=None, **kwargs):
        rows = fixture_records() if rows is None else rows
        root = self.directory()
        result = extract(lambda: iter(deepcopy(rows)), self.config, root, rows_per_shard=2, **kwargs)
        return result, root

    def test_exact_coordinates_gaps_duplicate_order_and_batch_lookup(self):
        index = self.index()
        rows = [dict(id=i, lon=x, lat=y) for i, x, y in [(1, -180., -90.), (100, -.0000001, .0000001), (2**62, 180., 90.)]]
        for row in rows:
            index.add(row)
        index.finish()
        self.assertEqual(index.points([2**62, 1, 100, 100]), [[180., 90.], [-180., -90.], [-.0000001, .0000001], [-.0000001, .0000001]])
        for identity in (2, 101, 2**62 + 1):
            with self.assertRaises(PilotError):
                index.points([identity])
        index.finish()
        index.close()
        index.close()
        with self.assertRaises(PilotError):
            index.points([1])

    def test_precision_negative_zero_types_and_coordinate_bounds_rejected(self):
        for value, bound in [(-0., 180), (.123456789, 180), (float('nan'), 180), (float('inf'), 180), (181., 180), (91., 90), (True, 180)]:
            with self.assertRaises(PilotError):
                coordinate(value, bound)
        for value in (-180., -1., 0., .1234567, 180.):
            self.assertEqual(struct.pack('<d', coordinate(value, 180) / 10000000), struct.pack('<d', value))

    def test_writer_order_identity_overwrite_and_unfinished_lookup(self):
        index = self.index()
        index.add({'id': 2, 'lon': 1., 'lat': 2.})
        for identity in (2, 1, 0, True, 2**63):
            with self.assertRaises(PilotError):
                index.add({'id': identity, 'lon': 1., 'lat': 2.})
        with self.assertRaises(PilotError):
            index.points([2])
        index.finish()
        with self.assertRaises(FileExistsError):
            Index(index.root, index.storage)

    def test_corrupt_truncated_symlink_and_catalog_limits(self):
        for damage in ('corrupt', 'truncate', 'symlink'):
            index = self.index()
            index.add({'id': 1, 'lon': 1., 'lat': 2.})
            index.finish()
            path = index.path(0)
            raw = path.read_bytes()
            path.unlink()
            if damage == 'symlink':
                target = index.root / 'target'
                target.write_bytes(raw)
                path.symlink_to(target)
            else:
                path.write_bytes(raw[:-1] if damage == 'truncate' else raw[:-1] + bytes([raw[-1] ^ 1]))
            with self.assertRaises(PilotError):
                index.points([1])
        index = self.index(catalog_limit=100)
        index.add({'id': 1, 'lon': 1., 'lat': 2.})
        with self.assertRaises(PilotError):
            index.finish()

    def test_file_index_and_shared_peak_limits_before_write(self):
        for storage, limit in [(Storage(10000, 80), 1000), (Storage(80, 10000), 1000), (Storage(10000, 10000), 80)]:
            index = Index(self.directory() / 'index', storage, index_limit=limit)
            index.add({'id': 1, 'lon': 1., 'lat': 2.})
            with self.assertRaises(PilotError):
                index.finish()
            self.assertLessEqual(storage.live, storage.limit)

    def test_rolling_independent_shard_replacement_and_drift(self):
        for drift in (False, True):
            first = self.index()
            rows = [{'id': i + 1, 'lon': float(i), 'lat': 1.} for i in range(5)]
            for row in rows:
                first.add(row)
            first.finish()
            second = Index(first.root.parent / 'audit', first.storage, rows_per_shard=2, replacing=first)
            copied = deepcopy(rows)
            if drift:
                copied[0]['lon'] += 1
                with self.assertRaises(PilotError):
                    for row in copied:
                        second.add(row)
                self.assertTrue(first.path(0).exists())
            else:
                before = first.storage.live
                for row in copied:
                    second.add(row)
                second.finish()
                self.assertFalse(any(first.root.glob('*.bin')))
                self.assertEqual(second.points([1, 5]), [[0., 1.], [4., 1.]])
                self.assertLess(first.storage.peak, 2 * before)

    def test_two_pass_output_matches_frozen_four_pass_reference(self):
        result, root = self.run_extract()
        self.assertEqual(result['status'], 'passed_two_pass_prototype', result)
        self.assertTrue(result['independentAuditComplete'])
        self.assertEqual(result['scanObjectVisits'], 18)
        self.assertEqual(len(result['passes']), 2)
        old_root = self.directory()
        reference = reference_extract(lambda: iter(fixture_records()), self.config, old_root, source_identity={'publisherStateUtc': STATE})
        self.assertTrue(reference['independentAuditComplete'])
        self.assertEqual((root / 'elements.jsonl').read_bytes(), (old_root / 'elements.jsonl').read_bytes())
        self.assertEqual(reference['scanObjectVisits'], 36)

    def test_primary_omitted_way_all_keys_extra_node_and_member_omission_fail_audit(self):
        def remove_all(selection):
            selection.keys.clear()
            for keys in selection.members.values():
                keys.clear()
        def remove_way(selection):
            selection.keys.remove(('way', 1))
            for keys in selection.members.values():
                keys.discard(('way', 1))
        def remove_node(selection):
            selection.keys.remove(('node', 2))
            for keys in selection.members.values():
                keys.discard(('node', 2))
        def extra_node(selection):
            selection.add('a', ('node', 3))
        for hook in (remove_all, remove_way, remove_node, extra_node):
            result, root = self.run_extract(primary_hook=hook)
            self.assertEqual(result['status'], 'stopped')
            self.assertFalse(result['independentAuditComplete'])
            self.assertTrue('audit' in result['error'].lower() or 'independent' in result['error'].lower(), result['error'])

    def test_primary_membership_and_geometry_tampering_are_rejected(self):
        def wrong_window(selection):
            selection.members['b'].clear()
        with patch('coarse_osm_stream_v1.intersects', return_value=False):
            result, _ = self.run_extract()
            self.assertEqual(result['status'], 'stopped')
        result, _ = self.run_extract(primary_hook=wrong_window)
        self.assertEqual(result['status'], 'stopped')

    def test_metadata_coordinate_and_count_drift_between_passes(self):
        for change in ('coordinate', 'tags', 'count'):
            calls = 0
            def reader():
                nonlocal calls
                rows = fixture_records()
                calls += 1
                if calls == 2:
                    if change == 'coordinate': rows[0]['lon'] += 1
                    elif change == 'tags': rows[3]['tags']['x'] = 'changed'
                    else: rows.pop()
                return iter(rows)
            result = extract(reader, self.config, self.directory(), rows_per_shard=2)
            self.assertEqual(result['status'], 'stopped')

    def test_omitted_restriction_and_corrupted_output_rejected(self):
        def omit_relation(selection, snapshot):
            yield from (r for r in reference_records(selection, snapshot) if r['element']['type'] != 'relation')
        with patch('coarse_osm_stream_v1.records', omit_relation):
            result, _ = self.run_extract()
            self.assertEqual(result['status'], 'stopped')
            self.assertIn('Independent', result['error'])
        def changed_tag(selection, snapshot):
            for row in reference_records(selection, snapshot):
                row['element']['tags']['changed'] = 'yes'
                yield row
        with patch('coarse_osm_stream_v1.records', changed_tag):
            result, _ = self.run_extract()
            self.assertEqual(result['status'], 'stopped')
            self.assertIn('Independent', result['error'])

    def test_deadline_during_reader(self):
        self.config['proposedCaps']['wallSeconds'] = .01
        def slow():
            time.sleep(.1)
            yield fixture_records()[0]
        result = extract(slow, self.config, self.directory())
        self.assertEqual(result['status'], 'stopped')
        self.assertFalse(result['independentAuditComplete'])

    def test_fused_native_boundary_outcomes_match_reference(self):
        base = dict(id=1, version=1, timestamp=datetime.datetime(2026, 10, 20, tzinfo=datetime.timezone.utc), visible=True,
            tags=[], location=SimpleNamespace(lon=1., lat=2., x=10000000, y=20000000), type_str=lambda: 'n')
        cases = [base, base | {'id': 0}, base | {'version': 0}, base | {'visible': False},
            base | {'timestamp': datetime.datetime(2026, 10, 26, tzinfo=datetime.timezone.utc)},
            base | {'timestamp': base['timestamp'].replace(microsecond=1)},
            base | {'timestamp': base['timestamp'].replace(tzinfo=None)},
            base | {'timestamp': base['timestamp'].replace(year=1)},
            base | {'tags': [SimpleNamespace(k='x', v='a'), SimpleNamespace(k='x', v='b')]},
            base | {'type_str': lambda: 'w', 'nodes': [SimpleNamespace(ref=1)]},
            base | {'type_str': lambda: 'w', 'nodes': [SimpleNamespace(ref=1), SimpleNamespace(ref=0)]},
            base | {'type_str': lambda: 'r', 'members': [SimpleNamespace(type='w', ref=-1, role='from')]}]
        for values in cases:
            outcomes = []
            for implementation in ('reference', 'candidate'):
                try:
                    obj = SimpleNamespace(**values)
                    if implementation == 'reference':
                        raw = reference_project(obj, 1048576)
                        run = Run(self.directory(), self.config)
                        list(reference_checked(lambda: iter([raw]), run, STATE, 'boundary'))
                    else:
                        validator = NativeValidator(STATE, 1048576, self.config['proposedCaps'], lambda raw, line: None)
                        validator.see(obj)
                    outcomes.append(True)
                except Exception:
                    outcomes.append(False)
            self.assertEqual(outcomes[0], outcomes[1], values)

    def test_profile_decoder_failure_retains_partial_counters(self):
        from profile_osm_stream_v1 import benchmark
        def broken(path, validator):
            validator.counts['node'] = 1
            validator.visits = 1
            raise ValueError('native decode stopped')
        root = self.directory() / 'case'
        with patch('profile_osm_stream_v1.native_scan', broken):
            with self.assertRaisesRegex(ValueError, 'native decode stopped'):
                benchmark('synthetic', self.config, root, 'validation', lambda: None)
        partial = json.loads((root / 'partial-result.json').read_text())
        self.assertEqual(partial['nativeDeliveredCounts'], {'node': 1})
        self.assertFalse(partial['nativePrefixEof'])
        self.assertFalse(partial['indexesTrusted'])

    def test_malformed_caps_and_decoder_failure_never_claim_eof(self):
        for change in ('reference', 'timestamp', 'order', 'byte', 'visit', 'selected', 'retained', 'output'):
            rows = fixture_records()
            config = deepcopy(self.config)
            if change == 'reference': rows[4]['nodes'][0] = 999
            elif change == 'timestamp': rows[0]['timestamp'] = '2026-02-30T00:00:00Z'
            elif change == 'order': rows[1]['id'] = 1
            else:
                cap = {'byte': 'singleNormalizedElementBytes', 'visit': 'scanObjectVisitsTotal', 'selected': 'selectedUniqueTypedElements', 'retained': 'retainedNativeObjectBytes', 'output': 'normalizedExtractBytes'}[change]
                config['proposedCaps'][cap] = 1
            result = extract(lambda: iter(rows), config, self.directory(), rows_per_shard=2)
            self.assertEqual(result['status'], 'stopped', change)
            self.assertFalse(result['independentAuditComplete'])
        def broken():
            yield fixture_records()[0]
            raise ValueError('decoder failed')
        result = extract(broken, self.config, self.directory())
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['passes'][0]['status'], 'running')

    @unittest.skipIf(osmium is None, 'Qualified native tools are isolated to Linux')
    def test_native_coordinate_exactness_and_projection_equivalence(self):
        rng = random.Random(731)
        for _ in range(5000):
            location = osmium.osm.Location(rng.randint(-1800000000, 1800000000) / 10000000, rng.randint(-900000000, 900000000) / 10000000)
            self.assertEqual(coordinate(location.lon, 180), location.x)
            self.assertEqual(coordinate(location.lat, 90), location.y)
        root = self.directory()
        xml, pbf = root / 'fixture.osm', root / 'fixture.pbf'
        write_xml(xml, fixture_records())
        with osmium.SimpleWriter(str(pbf)) as writer:
            for obj in osmium.FileProcessor(str(xml)):
                writer.add(obj)
        actual = []
        validator = NativeValidator(STATE, 1048576, self.config['proposedCaps'], lambda raw, line: actual.append(raw))
        native_scan(pbf, validator)
        self.assertTrue(validator.eof)
        self.assertEqual(actual, list(native_records(pbf, 1048576)))
        truncated = root / 'truncated.pbf'
        truncated.write_bytes(pbf.read_bytes()[:-1])
        validator = NativeValidator(STATE, 1048576, self.config['proposedCaps'], lambda raw, line: None)
        with self.assertRaises(Exception):
            native_scan(truncated, validator)
        self.assertFalse(validator.eof)


if __name__ == '__main__':
    unittest.main()
