"""Synthetic-only summary/probe controls; compiled cases require the target ABI."""
from copy import deepcopy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_projector_v1_test as prior
import coarse_osm_sample_v1_test as sample_controls
from coarse_osm_country_screen_v1 import (NativeScreen, BoundedCodec, Census, OwnedStorage, ProbeReader, RECEIPT_NAMES,
                                        LIMIT_NAMES, XY, default_limits, priority, strata, audit_probe, lookup, run_pair, resource_metrics)
from coarse_osm_delta_v1 import Index, ReferenceCodec, BLOCK, ROWS
from coarse_osm_projector_v1 import BLOCK_EVENT, CALLBACK, field_frame, framed_records, reference_seal
from coarse_osm_native_smoke import fixture_records, STATE
from coarse_osm_records import canonical
from coarse_timing_input import PilotError

ARTIFACT = None
ENGINES = []


def configure_native(path, sha):
    global ARTIFACT
    ARTIFACT = (path, sha)


def binding(path):
    body = Path(path).read_bytes()
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'md5': hashlib.md5(body).hexdigest()}


def block_event(rows):
    payload = ReferenceCodec().encode(rows)
    return BLOCK_EVENT.pack(len(rows), rows[0][0], rows[-1][0], len(payload))+payload


class HostTests(unittest.TestCase):
    def test_strata_are_fixed_ordinals_and_small_fixture_cases(self):
        self.assertEqual(strata(766), [0, 109, 218, 327, 437, 546, 655, 765])
        self.assertEqual(strata(4), [0, 1, 2, 3])
        for size in (0, 767, True):
            with self.assertRaises(PilotError):
                strata(size)

    def test_priority_vectors_and_stable_tie_order(self):
        vectors = {1: 2347232807671798036, 2: 606183006175938884, 127: 14582558847513835711,
                   2147483648: 2766385720969411232, 9223372036854775807: 16075191014247825066}
        self.assertEqual({key: priority(key) for key in vectors}, vectors)
        self.assertEqual(sorted([(4, 3, 9), (4, 2, 8), (4, 2, 7)]), [(4, 2, 7), (4, 2, 8), (4, 3, 9)])

    def test_owned_storage_refuses_unowned_paths_overwrite_hardlinks_and_caps(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            store = OwnedStorage(root, limit=4*1024**2, file_limit=4)
            store.write(root/'one', b'abcd')
            with self.assertRaises(PilotError):
                store.write(root/'one', b'abcd')
            with self.assertRaises(PilotError):
                store.write(root/'big', b'abcde')
            other = root/'other'
            other.write_bytes(b'xxxx')
            with self.assertRaises(PilotError):
                store.remove(other, 4)
            with self.assertRaises(PilotError):
                store.write(root.parent/'outside', b'x')
            store.remove(root/'one', 4)
            self.assertEqual(store.live, 0)
            os.link(other, root/'link')
            with self.assertRaises(PilotError):
                store.write(root/'new', b'x')

    def test_allocation_namespace_and_missing_metrics_stop(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            store = OwnedStorage(root, limit=1, file_limit=64)
            with self.assertRaises(PilotError):
                store.write(root/'x', b'x')
            store = OwnedStorage(root, limit=4*1024**2, entries=1)
            with self.assertRaises(PilotError):
                store.write(root/'x', b'x')
            with self.assertRaises(PilotError):
                resource_metrics(root)

    def test_driver_refuses_national_phase_and_input_mounts(self):
        from run_osm_country_screen_v1 import validate
        repo = Path(__file__).resolve().parents[1]
        path = Path('/inputs/recipe.json') if Path('/inputs/recipe.json').exists() else repo/'docs/evidence/coarse-osm-country-helper-2026-10-30/qualification-plan.json'
        if not path.exists():
            self.skipTest('New qualification recipe is not frozen yet')
        plan = json.loads(path.read_text())
        validate(plan)
        bad = deepcopy(plan)
        bad['mounts']['data/coarse-quality/us-osm-input-v3/download/http/001.bin'] = '/source.pbf'
        with self.assertRaises(PilotError):
            validate(bad)
        bad = deepcopy(plan)
        bad['phase'] = 'national'
        with self.assertRaises(PilotError):
            validate(bad)


class NativeTests(unittest.TestCase):
    setUp = prior.Tests.setUp
    directory = prior.Tests.directory
    pbf = prior.Tests.pbf

    def engine(self, **kwargs):
        if ARTIFACT is None:
            self.skipTest('Compiled target country-screen helper required')
        engine = NativeScreen(*ARTIFACT, **kwargs)
        ENGINES.append(engine)
        return engine

    # Exercise the new compiled validator using the frozen independent outcomes.
    test_scalar_calendar_order = prior.Tests.test_native_scalar_calendar_order_state_outcomes_match_frozen_validator
    test_utf8_duplicates_copy = prior.Tests.test_native_utf8_duplicates_and_incremental_copy_limits
    test_canonical_fallback = prior.Tests.test_native_exact_canonical_caps_and_node_fallback_match_reference
    test_refs_members_xy_receipts = prior.Tests.test_native_refs_members_xy_and_visit_quotas_reject_before_filtering
    test_callback_failure_reentry_truncation = prior.Tests.test_native_callback_lifetimes_failure_reentrancy_and_truncated_wire
    test_fast_node_blocks = prior.Tests.test_native_fast_nodes_handoff_has_no_python_node_projection
    test_pbf_fields_framing_epoch = prior.Tests.test_actual_synthetic_pbf_fields_epoch_and_framing_match_frozen_projector
    test_posthash_source_drift = prior.Tests.test_native_pbf_post_scan_content_hash_refuses_same_metadata_overwrite
    test_discarded_node_metadata = prior.Tests.test_unselected_metadata_is_validated_and_bound_by_semantic_seal
    test_seeded_float_bits = sample_controls.Tests.test_seeded_native_float_bits_and_exact_near_caps_match_reference
    test_wire_types_reserved_and_copy = sample_controls.Tests.test_native_wire_unknown_type_member_reserved_and_copy_bounds

    def test_summary_and_full_field_modes_seal_every_type(self):
        rows = fixture_records()
        rows[0]['tags'] = {'unicode': 'é😀\x7f'}
        engine = self.engine()
        traces = []
        result = engine.validate_frames(framed_records(rows), STATE, self.caps, on_trace=traces.append)
        self.assertEqual(result['counts'], {'node': 4, 'way': 3, 'relation': 2})
        self.assertEqual(result['pythonProjectionFrames'], 0)
        self.assertEqual(result['semanticSha256'], reference_seal(rows))
        self.assertEqual(result['references'], 6)
        self.assertEqual(result['members'], 4)
        self.assertEqual(result['sourceEncodeRows'], 4)
        self.assertEqual(result['sourceDecodeRows'], 4)
        self.assertEqual(result['sourceCodecCalls'], 2)
        actual = []
        proof = engine.validate_frames(framed_records(rows), STATE, self.caps, proof=True, on_record=actual.append)
        self.assertEqual(actual, rows)
        self.assertEqual(proof['semanticSha256'], result['semanticSha256'])
        for row in rows[4:]:
            broken = dict(row, visible=False)
            with self.assertRaises(PilotError):
                engine.validate_frames(framed_records([broken]), STATE, self.caps)
            self.assertFalse(engine.last['nativeEof'])

    def test_real_checked_u64_operations_and_abi_lengths(self):
        engine = self.engine()
        add = engine.library.gp_country_screen_add
        add.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64)]
        add.restype = ctypes.c_int
        for start in (2**31-1, 2**32-1, 2**64-2):
            out = ctypes.c_uint64()
            self.assertEqual(add(start, 1, ctypes.byref(out)), 0)
            self.assertEqual(out.value, start+1)
        out = ctypes.c_uint64(123)
        self.assertNotEqual(add(2**64-1, 1, ctypes.byref(out)), 0)
        self.assertEqual(out.value, 123)
        self.assertNotEqual(add(0, 0, None), 0)
        function = engine.library.gp_country_screen_priority
        function.argtypes = [ctypes.c_uint64]
        function.restype = ctypes.c_uint64
        for key in (1, 2, 127, 2**31, 2**63-1):
            self.assertEqual(function(key), priority(key))
        ordinal = engine.library.gp_country_screen_stratum
        ordinal.argtypes = [ctypes.c_uint64, ctypes.c_uint64]
        ordinal.restype = ctypes.c_uint64
        self.assertEqual([ordinal(766, k) for k in range(8)], strata(766))
        self.assertEqual(ordinal(0, 0), 2**64-1)
        receipt = (ctypes.c_uint64*len(RECEIPT_NAMES))()
        error = ctypes.create_string_buffer(512)
        values = (ctypes.c_uint64*len(LIMIT_NAMES))(*default_limits(self.caps).values())
        raw = ctypes.create_string_buffer(b'')
        for supplied in (None, values):
            code = engine.frames(raw, 0, STATE.encode(), 1048576, supplied, 4, 0, None, 0, CALLBACK(), None,
                                 receipt, len(receipt), error, len(error))
            self.assertNotEqual(code, 0)
            self.assertFalse(receipt[4])

    def test_new_linked_codec_matches_reference_across_signed63_gaps(self):
        engine = self.engine()
        rows = [(1, -1800000000, -900000000), (2**31, 0, 0), (2**40, -1, 1), (2**63-1, 1800000000, 900000000)]
        encoded = engine.codec.encode(rows)
        self.assertEqual(encoded, ReferenceCodec().encode(rows))
        self.assertEqual(engine.codec.decode(encoded, 4, 1, 2**63-1), rows)
        with self.assertRaises(PilotError):
            engine.codec.decode(encoded[:-1], 4, 1, 2**63-1)
        raw = [dict(fixture_records()[0], id=i, lon=x/10000000, lat=y/10000000, tags={}) for i, x, y in rows]
        blocks = []
        receipt = engine.validate_frames(framed_records(raw), STATE, self.caps, on_block=blocks.append)
        self.assertEqual(receipt['maxNodeId'], 2**63-1)
        self.assertEqual(blocks[0][BLOCK_EVENT.size:], encoded)

    def test_cap_plus_one_and_counter_limits_count_rejected_objects(self):
        rows = fixture_records()
        for key, bound in [('scanNodesPerPass', 1), ('scanObjectVisitsTotal', 1)]:
            engine = self.engine()
            with self.assertRaises(PilotError):
                engine.validate_frames(framed_records(rows[:2]), STATE, dict(self.caps, **{key: bound}))
            self.assertEqual(engine.last['visits'], 2)
        engine = self.engine(aggregate_visits=1)
        with self.assertRaises(PilotError):
            engine.validate_frames(framed_records(rows[:2]), STATE, self.caps)
        self.assertEqual(engine.visits, 2)
        for name, limit, case in [('references', 1, rows[4:5]), ('members', 1, rows[7:8]),
                                  ('semanticBytes', 1, rows[:1]), ('sourceCodecRows', 1, rows[:1]),
                                  ('sourceCodecCalls', 1, rows[:1])]:
            engine = self.engine()
            limits = default_limits(self.caps)
            limits[name] = limit
            with self.assertRaises(PilotError):
                engine.validate_frames(framed_records(case), STATE, self.caps, limits=limits)
            self.assertFalse(engine.last['nativeEof'])

    def test_fallback_count_limit_and_65536_checkpoint_cadence(self):
        row = dict(fixture_records()[0], tags={}, lon=0., lat=0.)
        engine = self.engine()
        limits = default_limits(self.caps)
        limits['fallbackFrames'] = 1
        caps = dict(self.caps, singleNormalizedElementBytes=len(canonical(row)))
        with self.assertRaises(PilotError):
            engine.validate_frames(framed_records([row, dict(row, id=2)]), STATE, caps, limits=limits)
        self.assertEqual(engine.last['fallbacks'], 2)
        rows = [dict(row, id=i+1) for i in range(65537)]
        result = self.engine().validate_frames(framed_records(rows), STATE, dict(self.caps, scanNodesPerPass=70000))
        self.assertEqual(result['checkpoints'], 2)
        self.assertEqual(result['blocks'], 17)

    def test_witness_typed_rows_are_from_source_and_missing_ids_stop(self):
        rows = fixture_records()
        engine = self.engine()
        output = bytearray()
        result = engine.validate_frames(framed_records(rows), STATE, self.caps, selected=[1, 4], on_witness=output.extend)
        self.assertEqual(list(XY.iter_unpack(output)), [(1, -10000000, 5000000), (4, -10000000, 20000000)])
        self.assertEqual(result['witnessRows'], 2)
        with self.assertRaisesRegex(PilotError, 'missing_witness'):
            engine.validate_frames(framed_records(rows), STATE, self.caps, selected=[5])
        for keys in ([1, 1], [4, 1], [0]):
            with self.assertRaises(PilotError):
                engine.validate_frames(b'', STATE, self.caps, selected=keys)

    def test_native_way_priority_top128_exclusions_and_bounds(self):
        nodes = [dict(fixture_records()[0], id=i+1, tags={}) for i in range(4)]
        ways = [dict(fixture_records()[4], id=i+1, tags={'highway': 'primary'}, nodes=[1, 4]) for i in range(200)]
        ways += [dict(ways[0], id=201, nodes=[1, 5]), dict(ways[0], id=202, nodes=[1]*1025), dict(ways[0], id=203, tags={})]
        trace = []
        result = self.engine().validate_frames(framed_records(nodes+ways), STATE, self.caps, on_trace=trace.append)
        expected = sorted(ways[:200], key=lambda row: (priority(row['id']), row['id']))[:128]
        self.assertEqual([r['wayID'] for r in trace], [r['id'] for r in expected])
        self.assertEqual(result['eligibleHighwayWays'], 200)
        self.assertEqual(result['highwayWays'], 202)
        self.assertEqual(result['longHighwayWays'], 1)
        self.assertEqual(result['outOfRangeHighwayWays'], 1)
        self.assertEqual(result['nextExcludedId'], sorted(ways[:200], key=lambda row: (priority(row['id']), row['id']))[128]['id'])
        self.assertEqual(len(canonical(trace)) < 4*1024**2, True)

    def test_census_matches_full_reference_and_remaps_nonadjacent_shards(self):
        engine = self.engine()
        root = self.directory()
        store = OwnedStorage(root)
        rows = [(i*129+1, i, -i) for i in range(37)]
        census = Census(root/'summary', store, engine.codec, len(rows), blocks_per_shard=2, fixture_rows=2)
        reference = Index(root/'reference', store, codec=ReferenceCodec(), blocks_per_shard=2, index_limit=33554432)
        for offset in range(0, len(rows), 2):
            block = rows[offset:offset+2]
            census.append(block_event(block))
            for identity, x, y in block:
                reference.add_xy(identity, x, y)
            reference.flush_block()
        reference.finish()
        result = census.finish()
        self.assertEqual(result['globalManifest'], reference.reader.manifest)
        self.assertEqual(result['logicalWholeIndexBytes'], reference.generated_bytes)
        self.assertEqual((root/'summary/global-directory.bin').read_bytes(), (root/'reference/directory.bin').read_bytes())
        self.assertEqual(len(census.mapping), 8)
        self.assertTrue(any(x['source'] != x['mini'] for x in census.mapping))
        self.assertEqual(audit_probe(census.mini.root)['rows'], census.mini.count)
        replacement = Census(root/'replacement', store, engine.codec, len(rows), replacing=census, blocks_per_shard=2, fixture_rows=2)
        for offset in range(0, len(rows), 2):
            replacement.append(block_event(rows[offset:offset+2]))
        self.assertEqual(replacement.finish()['globalManifest'], result['globalManifest'])
        self.assertEqual(replacement.mini.reader.manifest, census.mini.reader.manifest)
        self.assertFalse((census.mini.root/'00000000.bin').exists())
        self.assertTrue((root/'reference/00000000.bin').exists())

    def test_census_caps_missing_or_partial_blocks_and_bad_replacement_refuse(self):
        engine = self.engine()
        for kwargs in ({'directory_limit': 128}, {'catalog_limit': 1}, {'probe_limit': 1}):
            root = self.directory()
            census = Census(root/'s', OwnedStorage(root), engine.codec, 2, **kwargs)
            with self.assertRaises(PilotError):
                census.append(block_event([(1, 0, 0), (2, 1, 1)]))
                census.finish()
        root = self.directory()
        census = Census(root/'s', OwnedStorage(root), engine.codec, 4)
        census.append(block_event([(1, 0, 0)]))
        with self.assertRaises(PilotError):
            census.append(block_event([(2, 0, 0)]))
        with self.assertRaises(PilotError):
            census.finish()
        root = self.directory()
        store = OwnedStorage(root)
        first = Census(root/'a', store, engine.codec, 1)
        first.append(block_event([(1, 0, 0)]))
        first.finish()
        second = Census(root/'b', store, engine.codec, 1, replacing=first)
        second.append(block_event([(1, 1, 0)]))
        with self.assertRaises(PilotError):
            second.finish()
        self.assertTrue((first.mini.root/'00000000.bin').exists())

    def test_lookup_cache_pressure_source_bits_and_warm_integrity(self):
        engine = self.engine(codec_rows=2000000)
        root = self.directory()
        store = OwnedStorage(root)
        total = 70*4096
        census = Census(root/'s', store, engine.codec, total)
        witness = bytearray()
        for offset in range(0, total, 4096):
            rows = [(i+1, i%100, -(i%100)) for i in range(offset, offset+4096)]
            census.append(block_event(rows))
            witness.extend(XY.pack(*rows[0]))
        census.finish()
        keys = [row[0] for row in XY.iter_unpack(witness)]
        codec = BoundedCodec(*ARTIFACT, row_budget=2000000)
        result = lookup(census.mini.root, codec, [[keys[0]], keys+keys[:1], []], witness)
        spread = [r for r in result['runs'] if r['cohort'] == 'spread']
        self.assertTrue(all(r['misses'] >= 70 and r['evictions'] > 0 for r in spread))
        self.assertEqual(len({r['coordinateBitsSha256'] for r in spread}), 1)
        self.assertGreater(spread[1]['authenticatedShardBytes'], 0)
        with self.assertRaises(PilotError):
            lookup(census.mini.root, BoundedCodec(*ARTIFACT), [[keys[0]], [], []], witness, read_limit=1)
        reader = ProbeReader(census.mini.root, ReferenceCodec())
        reader.points([1])
        path = reader.path(0)
        stamp = path.stat()
        body = path.read_bytes()
        path.write_bytes(body[:-1]+bytes([body[-1]^1]))
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaises(PilotError):
            reader.points([1])
        reader.close()

    def test_two_guarded_source_passes_and_independent_probe_audit(self):
        engine = self.engine()
        nodes = [dict(fixture_records()[0], id=i+1, tags={}) for i in range(300)]
        ways = [dict(fixture_records()[4], id=i+1, tags={'highway': 'primary'}, nodes=[i%299+1, i%299+2]) for i in range(200)]
        path = self.pbf(nodes+ways)
        result = run_pair(path, {'node': 300, 'way': 200, 'relation': 0}, self.caps, STATE,
                          self.directory()/'pair', engine, binding(path))
        self.assertEqual(result['objectReceipts'], 1000)
        self.assertEqual(result['referenceAudit']['rows'], 300)
        self.assertEqual(result['passes'][0]['receipt']['semanticSha256'], result['passes'][1]['receipt']['semanticSha256'])
        self.assertEqual(result['passes'][0]['receipt']['traceWays'], 128)
        self.assertTrue(all(p['receipt']['knownGuardReadBytes'] == 2*path.stat().st_size for p in result['passes']))

    def test_insufficient_trace_and_between_pass_drift_are_untrusted(self):
        self.engine()
        path = self.pbf()
        root = self.directory()/'insufficient'
        with self.assertRaises(PilotError):
            run_pair(path, {'node': 4, 'way': 3, 'relation': 2}, self.caps, STATE, root, self.engine(), binding(path))
        self.assertFalse(json.loads((root/'partial-result.json').read_text())['eof'])
        root = self.directory()/'drift'
        def change():
            body = path.read_bytes()
            path.write_bytes(body[:-1]+bytes([body[-1]^1]))
        with self.assertRaises(Exception):
            run_pair(path, {'node': 4, 'way': 3, 'relation': 2}, self.caps, STATE, root, self.engine(), binding(path), minimum_ways=0, before_second=change)
        self.assertFalse(json.loads((root/'partial-result.json').read_text())['indexesTrusted'])

    def test_hard_watchdog_kills_native_framing_and_posthash_stalls(self):
        self.engine()
        path = self.pbf()
        program = """import ctypes,sys,time
import coarse_osm_country_screen_v1 as module
from coarse_osm_country_screen_v1 import NativeScreen
from coarse_osm_native_smoke import STATE
from coarse_timing_input import start_watchdog
engine=NativeScreen(sys.argv[1],sys.argv[2])
phase=sys.argv[4]
caps={'singleNormalizedElementBytes':1048576,'scanNodesPerPass':100,'scanWaysPerPass':100,'scanRelationsPerPass':100,'scanObjectVisitsTotal':100,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
if phase=='framing':module.framing=lambda *a,**k:time.sleep(10)
def check():
 if phase=='posthash' and not engine.active and engine.last is not None:time.sleep(10)
start_watchdog(.2)
if phase=='no-callback':ctypes.CDLL(None).pause()
else:engine.scan(sys.argv[3],STATE,caps,proof=True,on_record=lambda row:time.sleep(10) if phase=='native-callback' else None,check=check)
"""
        for phase in ('native-callback', 'no-callback', 'framing', 'posthash'):
            result = subprocess.run([sys.executable, '-B', '-c', program, *ARTIFACT, str(path), phase],
                                    capture_output=True, timeout=5, env=os.environ | {'PYTHONPATH': os.pathsep.join(sys.path)})
            self.assertEqual(result.returncode, -9, (phase, result.stderr))


if __name__ == '__main__':
    unittest.main()
