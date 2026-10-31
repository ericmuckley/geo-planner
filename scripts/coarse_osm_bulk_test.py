"""Synthetic controls/extraction tests. No Pyosmium binary or road data."""
from contextlib import nullcontext
from copy import deepcopy
import datetime
import hashlib
import http.client
import io
import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
import zlib

from coarse_osm_bulk import Coordinates, Run, extract, extract_pbf
from coarse_osm_bulk_audit import crossing
from coarse_osm_bulk_pbf import fields, framing, native_records
from coarse_osm_bulk_transport import Https, Meter, unpack_wheel, validate_lock, wheel_lock, packaging_api
from coarse_osm_records import canonical
from coarse_timing_input import PilotError
from prepare_osm_bulk import validate_plan, resolve


REPO = Path(__file__).resolve().parents[1]
PROPOSAL = REPO / 'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
STATE = '2026-10-25T21:21:21Z'


def objects():
    common = {'version': 1, 'timestamp': '2026-10-20T00:00:00Z'}
    return [
        {'type': 'node', 'id': 1, **common, 'lon': -1., 'lat': .5, 'tags': {'barrier': 'gate'}},
        {'type': 'node', 'id': 2, **common, 'lon': 2., 'lat': .5},
        {'type': 'node', 'id': 3, **common, 'lon': -2., 'lat': 2.},
        {'type': 'node', 'id': 4, **common, 'lon': -1., 'lat': 2.},
        {'type': 'way', 'id': 1, **common, 'nodes': [1, 2], 'tags': {'highway': 'primary', 'maxspeed': '55 mph', 'access': 'private', 'maxspeed:conditional': '35 @ wet'}},
        {'type': 'way', 'id': 3, **common, 'nodes': [3, 4], 'tags': {'highway': 'secondary'}},
        {'type': 'way', 'id': 4, **common, 'nodes': [3, 4], 'tags': {'waterway': 'stream'}},
        {'type': 'relation', 'id': 1, **common, 'tags': {'type': 'restriction', 'restriction:conditional': 'no_left_turn @ wet'},
            'members': [{'type': 'way', 'ref': 1, 'role': 'from'}, {'type': 'node', 'ref': 2, 'role': 'via'}, {'type': 'way', 'ref': 999, 'role': 'to'}]},
        {'type': 'relation', 'id': 2, **common, 'tags': {'type': 'restriction'}, 'members': [{'type': 'way', 'ref': 3, 'role': 'from'}]}]


def varint(n):
    out = bytearray()
    while n > 127: out.append((n & 127) | 128); n >>= 7
    out.append(n); return bytes(out)


def field(n, value):
    return varint(n * 8) + varint(value) if isinstance(value, int) else varint(n * 8 + 2) + varint(len(value)) + value


def frame(kind, payload, compressed=False):
    blob = field(2, len(payload)) + field(3, zlib.compress(payload)) if compressed else field(1, payload)
    header = field(1, kind) + field(3, len(blob))
    return struct.pack('!I', len(header)) + header + blob


def pbf(features=None, compressed=False):
    timestamp = int(datetime.datetime.fromisoformat(STATE.replace('Z', '+00:00')).timestamp())
    header = b''.join(field(4, f.encode()) for f in features or ['OsmSchema-V0.6', 'DenseNodes']) + field(32, timestamp)
    return frame(b'OSMHeader', header, compressed) + frame(b'OSMData', field(1, b''), compressed)


class Response:
    def __init__(self, body=b'abc', status=200, headers=None, length=True, on_read=None, partial=None):
        self.status = status; self.headers = [('Content-Length', str(len(body)))] if length else []
        self.headers += headers or []; self.body = io.BytesIO(body); self.closed = False; self.on_read = on_read; self.partial = partial
    def read1(self, size):
        if self.on_read: self.on_read()
        if self.partial is not None:
            partial, self.partial = self.partial, None; raise http.client.IncompleteRead(partial, 1)
        return self.body.read(size)
    def close(self): self.closed = True


class Transport:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def open(self, *args):
        self.calls.append(args); result = self.responses.pop(0)
        if isinstance(result, Exception): raise result
        return result


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name); self.serial = 0
        self.proposal = json.loads(PROPOSAL.read_text()); c = self.proposal['proposedCaps']
        c.update(sqliteIndexBytesEach=1048576, sqliteMaxPagesEach=256, sqliteCacheBytesEach=8192,
            workingBytesIncludingTmp=33554432, tmpBytes=65536, pythonSelectionStateBytes=4194304, retainedNativeObjectBytes=1048576,
            normalizedExtractBytes=1048576, scanNodesPerPass=100, scanWaysPerPass=100, scanRelationsPerPass=100, scanObjectVisitsTotal=1200)
        self.proposal['windows'] = [{'id': 'a', 'bbox': [0, 0, 1, 1]}, {'id': 'b', 'bbox': [.25, .25, .75, .75]}]
        self.identity = {'publisherStateUtc': STATE, 'kind': 'synthetic_iterator_not_qualified_decoder'}
    def directory(self):
        self.serial += 1; p = self.root / str(self.serial); p.mkdir(); return p
    def run_extract(self, rows=None, proposal=None, reader=None):
        root = self.directory(); rows = objects() if rows is None else rows
        state = extract(reader or (lambda: iter(deepcopy(rows))), proposal or self.proposal, root, source_identity=self.identity)
        return state, root
    def meter(self, response=None, **changes):
        caps = {'attempts': 1, 'totalBytes': 1000, 'kindBytes': {'metadata': 1000, 'wheel': 1000, 'pbf': 1000}, 'wallSeconds': 10, 'idleSeconds': 2, 'workingBytes': 16777216}
        caps.update(changes.pop('caps', {})); spec = {'url': 'https://pypi.org/pypi/requests/json', 'kind': 'metadata', 'maxBytes': 100, 'seconds': 2}; spec.update(changes.pop('spec', {}))
        transport = Transport([response or Response()]); m = Meter(self.directory(), [spec], caps, transport=transport, **changes)
        return m, transport

    def test_crossing_full_native_closure_and_independent_four_passes(self):
        state, root = self.run_extract(); self.assertEqual(state['status'], 'extracted_publisher_file_analysis_pending')
        rows = [json.loads(s) for s in (root / 'elements.jsonl').read_text().splitlines()]
        self.assertEqual({(r['element']['type'], r['element']['id']) for r in rows}, {('node', 1), ('node', 2), ('way', 1), ('relation', 1)})
        way = next(r for r in rows if r['element']['type'] == 'way'); self.assertEqual(way['windowIds'], ['a', 'b'])
        self.assertEqual(way['element']['tags']['access'], 'private'); self.assertIn('geometryDependencySha256', way)
        relation = next(r for r in rows if r['element']['type'] == 'relation'); self.assertEqual(relation['element']['members'][-1]['ref'], 999)
        self.assertEqual(state['scanObjectVisits'], 36); self.assertEqual(len(state['passes']), 4)
        self.assertFalse(state['sourceFeasibilityQualified']); self.assertFalse(state['nativeDecoderQualified'])
        self.assertTrue(json.loads((root / 'audit.json').read_text())['independentSelectionNativeIdentityAndOutputAudit'])

    def test_empty_source_is_empty_from_file_not_coverage(self):
        state, root = self.run_extract([]); self.assertEqual(state['status'], 'extracted_publisher_file_analysis_pending')
        self.assertEqual((root / 'elements.jsonl').read_bytes(), b''); self.assertFalse(state['publisherBoundaryQualified'])

    def test_documented_geometry_cases_independent_clip(self):
        data = json.loads((PROPOSAL.parent / 'synthetic-cases.json').read_text())
        for case in data['geometryCases']: self.assertEqual(crossing(case['points'], data['bbox']), case['selected'], case['name'])

    def test_node_geometry_changes_dependency_under_unchanged_way(self):
        _, a = self.run_extract(); data = objects(); data[0]['lon'] = -2.; data[0]['version'] = 2
        _, b = self.run_extract(data)
        def way(root): return next(json.loads(s) for s in (root / 'elements.jsonl').read_text().splitlines() if json.loads(s)['element']['type'] == 'way')
        self.assertNotEqual(way(a)['geometryDependencySha256'], way(b)['geometryDependencySha256'])
        self.assertEqual(way(a)['elementSha256'], way(b)['elementSha256'])

    def test_audit_does_not_use_primary_selection(self):
        with patch('coarse_osm_bulk.intersects', return_value=False): state, _ = self.run_extract()
        self.assertEqual(state['status'], 'stopped'); self.assertIn('Audit', state['error']); self.assertFalse(state['independentAuditComplete'])

    def test_audit_independent_reconstruction_detects_reader_drift(self):
        count = 0
        def reader():
            nonlocal count
            count += 1; rows = objects()
            if count >= 3: rows[4]['tags']['maxspeed'] = 'different'
            return iter(rows)
        state, _ = self.run_extract(reader=reader); self.assertEqual(state['status'], 'stopped'); self.assertIn('audit', state['error'])

    def test_missing_nodes_duplicate_order_and_bad_metadata_stop(self):
        variants = []
        r = objects(); r[4]['nodes'].append(999); variants.append(r)
        r = objects(); r.insert(1, deepcopy(r[0])); variants.append(r)
        r = objects(); r[0]['timestamp'] = '2030-01-01T00:00:00Z'; variants.append(r)
        r = objects(); r[4]['tags']['highway'] = ''; variants.append(r)
        r = objects(); r[0]['lat'] = float('nan'); variants.append(r)
        for rows in variants:
            with self.subTest(rows=rows):
                state, root = self.run_extract(rows); self.assertEqual(state['status'], 'stopped'); self.assertFalse((root / 'audit.json').exists())

    def test_selected_unique_occurrence_heap_native_and_scan_caps(self):
        for key, value in [('selectedUniqueTypedElements', 1), ('selectedWindowElementOccurrences', 1), ('pythonSelectionStateBytes', 100), ('retainedNativeObjectBytes', 1), ('scanNodesPerPass', 1), ('scanObjectVisitsTotal', 2)]:
            with self.subTest(key=key):
                p = deepcopy(self.proposal); p['proposedCaps'][key] = value
                state, _ = self.run_extract(proposal=p); self.assertEqual(state['status'], 'stopped'); self.assertFalse(state['sourceFeasibilityQualified'])

    def test_extract_cap_retains_valid_prefix(self):
        p = deepcopy(self.proposal); p['proposedCaps']['normalizedExtractBytes'] = 400
        state, root = self.run_extract(proposal=p); self.assertEqual(state['status'], 'stopped')
        lines = (root / 'elements.jsonl').read_bytes().splitlines(); self.assertTrue(lines); self.assertLess(len(lines), 4)
        for line in lines: json.loads(line)
        self.assertLessEqual((root / 'elements.jsonl').stat().st_size, 400)

    def test_global_absolute_deadline_interrupts_blocked_iterator(self):
        p = deepcopy(self.proposal); p['proposedCaps']['wallSeconds'] = .03
        def reader(): time.sleep(1); return iter(objects())
        state, _ = self.run_extract(proposal=p, reader=reader); self.assertEqual(state['status'], 'stopped'); self.assertIn('deadline', state['error'])

    def test_reuse_refused_and_source_drift_between_passes(self):
        _, root = self.run_extract()
        with self.assertRaises(PilotError): extract(lambda: iter(objects()), self.proposal, root, source_identity=self.identity)
        n = 0
        def reader():
            nonlocal n
            n += 1; rows = objects()
            if n > 1: rows[0]['lon'] -= 1
            return iter(rows)
        state, _ = self.run_extract(reader=reader); self.assertIn('changed', state['error'])

    def test_sqlite_page_cap_and_reuse_refusal(self):
        c = deepcopy(self.proposal['proposedCaps']); c.update(sqliteMaxPagesEach=4, sqliteIndexBytesEach=16384)
        path = self.root / 'index'; index = Coordinates(path, c)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                for i in range(10000): index.add({'id': i + 1, 'lon': .12345678, 'lat': .87654321})
        finally: index.close()
        self.assertLessEqual(path.stat().st_size, 16384)
        with self.assertRaises(FileExistsError): Coordinates(path, c)

    def test_pbf_raw_and_compressed_frames(self):
        for compressed in (False, True):
            raw = pbf(compressed=compressed); path = self.root / ('compressed' if compressed else 'raw'); path.write_bytes(raw)
            result = framing(path, self.proposal['proposedCaps'], STATE)
            self.assertEqual(result['frames'], 2); self.assertEqual(result['framingBytesRead'], len(raw)); self.assertEqual(result['sourceSha256'], hashlib.sha256(raw).hexdigest())

    def test_pbf_schema_history_duplicate_order_truncation_and_state(self):
        variants = [pbf(['OsmSchema-V0.6', 'HistoricalInformation']), pbf(['Unsupported']), pbf()[:-1], frame(b'OSMData', b'x'), pbf() + pbf()]
        for n, raw in enumerate(variants):
            path = self.root / str(n); path.write_bytes(raw)
            with self.assertRaises((PilotError, ValueError)): framing(path, self.proposal['proposedCaps'], STATE)
        path = self.root / 'state'; path.write_bytes(pbf())
        with self.assertRaises(PilotError): framing(path, self.proposal['proposedCaps'], '2026-10-21T00:00:00Z')

    def test_protobuf_malformed_and_compression_bomb_bound(self):
        for value in [b'\x80', b'\x00', b'\x0a\xff', b'\x08' + b'\xff' * 11]:
            with self.assertRaises((PilotError, ValueError)): list(fields(value))
        limit = deepcopy(self.proposal['proposedCaps']); limit['pbfUncompressedBlobBytesExclusiveMaximum'] = 256
        blob = field(2, 10) + field(3, zlib.compress(b'x' * 10000)); head = field(1, b'OSMData') + field(3, len(blob))
        path = self.root / 'bomb'; path.write_bytes(pbf() + struct.pack('!I', len(head)) + head + blob)
        with self.assertRaises(PilotError): framing(path, limit, STATE)

    def test_optional_native_wrapper_copies_expiring_view(self):
        stamp = datetime.datetime.fromisoformat('2026-10-20T00:00:00+00:00')
        tag = SimpleNamespace(k='access', v='private')
        obj = SimpleNamespace(type_str=lambda: 'n', id=1, version=1, timestamp=stamp, visible=True, tags=[tag], location=SimpleNamespace(lon=1., lat=2.))
        def factory(_):
            yield obj
            tag.v = 'changed'; obj.id = 2; yield obj
        with patch.dict(sys.modules, {'osmium': SimpleNamespace(FileProcessor=factory)}): data = list(native_records('unused', 1000))
        self.assertEqual(data[0]['id'], 1); self.assertEqual(data[0]['tags']['access'], 'private'); self.assertEqual(data[1]['tags']['access'], 'changed')

    def test_pbf_projection_pipeline_with_injected_decoder_not_qualified(self):
        path = self.root / 'source.pbf'; raw = pbf(); path.write_bytes(raw); p = deepcopy(self.proposal)
        p['source'].update(listedBodyBytes=len(raw), publisherMd5=hashlib.md5(raw).hexdigest())
        root = self.directory(); state = extract_pbf(path, p, root, native_factory=lambda *_: iter(objects()))
        self.assertEqual(state['status'], 'extracted_publisher_file_analysis_pending'); self.assertFalse(state['nativeDecoderQualified'])
        p['source']['publisherMd5'] = '0' * 32; root = self.directory()
        with self.assertRaises(PilotError): extract_pbf(path, p, root, native_factory=lambda *_: iter(objects()))
        self.assertTrue((root / 'preflight-failure.json').exists())
        self.assertEqual(len(json.loads((root / 'preflight-failure.json').read_text())['windows']), 2)

    def test_meter_complete_and_no_retry(self):
        m, t = self.meter(); self.assertEqual(m.fetch(0).read_bytes(), b'abc'); self.assertEqual(m.body_bytes, 3)
        self.assertEqual(m.events[0]['outcome'], 'complete')
        with self.assertRaises(PilotError): m.fetch(0)
        self.assertEqual(len(t.calls), 1)

    def test_meter_error_redirect_certificate_and_partial_preserved(self):
        for response in [Response(status=502), Response(status=302), RuntimeError('certificate verify failed'), Response(partial=b'ab')]:
            with self.subTest(response=response):
                m, t = self.meter(response)
                with self.assertRaises(Exception): m.fetch(0)
                self.assertTrue(m.failed); self.assertEqual(len(t.calls), 1)
                if isinstance(response, Response): self.assertTrue(response.closed)
                self.assertEqual((m.root / '001.bin').stat().st_size, m.events[0]['bodyBytes'])

    def test_meter_duplicate_framing_compression_declared_and_streamed_caps(self):
        variants = [Response(headers=[('Content-Length', '3')]), Response(headers=[('Content-Encoding', 'gzip')]), Response(headers=[('Transfer-Encoding', 'chunked')]), Response(b'x' * 101), Response(b'x' * 101, length=False)]
        for r in variants:
            m, _ = self.meter(r)
            with self.assertRaises(PilotError): m.fetch(0)
            self.assertTrue(m.failed); self.assertLessEqual(m.events[0]['bodyBytes'], 101)
        self.assertEqual(m.events[0]['bodyBytes'], 101)

    def test_meter_hash_exact_and_aggregate_caps(self):
        for change in [{'spec': {'sha256': '0' * 64}}, {'spec': {'exactBytes': 2}}, {'caps': {'totalBytes': 2}}, {'caps': {'kindBytes': {'metadata': 2, 'wheel': 0, 'pbf': 0}}}, {'caps': {'workingBytes': 8388608}}]:
            m, _ = self.meter(**change)
            with self.assertRaises(PilotError): m.fetch(0)

    def test_meter_absolute_elapsed_and_connect_failure(self):
        now = [0.]
        def advance(): now[0] = 3.
        m, _ = self.meter(Response(on_read=advance), clock=lambda: now[0], alarm=lambda _: nullcontext())
        with self.assertRaises(PilotError): m.fetch(0)
        self.assertEqual(m.events[0]['bodyBytes'], 3)
        m, _ = self.meter(TimeoutError('connect timeout'))
        with self.assertRaises(TimeoutError): m.fetch(0)
        self.assertTrue((m.root / 'http-ledger.json').exists())

    def test_actual_https_ignores_proxy_auth_and_redirect_handlers(self):
        response = SimpleNamespace(status=302, getheaders=lambda: [], close=lambda: None)
        connection = SimpleNamespace(request=lambda *a, **k: None, getresponse=lambda: response, close=lambda: None)
        with patch('http.client.HTTPSConnection', return_value=connection) as factory, patch.dict('os.environ', {'HTTPS_PROXY': 'http://invalid', 'HTTP_PROXY': 'http://invalid'}):
            value = Https().open('https://pypi.org/pypi/requests/json', 2, 1); self.assertEqual(value.status, 302)
            self.assertEqual(factory.call_args.args[:2], ('pypi.org', 443)); value.close()
        for url in ['http://pypi.org/x', 'https://user@pypi.org/x', 'https://evil.test/x', 'https://pypi.org/x?q=1']:
            with self.assertRaises(PilotError): Https().open(url, 2, 1)

    def package_metadata(self):
        Tag = __import__('pip._vendor.packaging.tags', fromlist=['Tag']).Tag; self.tags = [Tag('py3', 'none', 'any')]
        self.env = {'python_version': '3.13', 'python_full_version': '3.13.5', 'extra': '', 'sys_platform': 'linux'}
        def meta(name, deps):
            filename = name.replace('-', '_') + '-1.0-py3-none-any.whl'
            return {'info': {'name': name, 'version': '1.0', 'requires_python': '>=3.8', 'requires_dist': deps}, 'urls': [{'filename': filename, 'size': 100, 'url': 'https://files.pythonhosted.org/packages/aa/' + filename, 'digests': {'sha256': 'a' * 64}, 'packagetype': 'bdist_wheel', 'yanked': False}]}
        data = {'osmium': meta('osmium', ['requests>=1,<2', 'pytest; extra == "tests"']), 'requests': meta('requests', [])}
        self.pin = {'wheel': {k: data['osmium']['urls'][0][k] for k in ('filename', 'size', 'url')}, 'wheelSha256': 'a' * 64}; return data

    def test_dependency_lock_closure_markers_and_tamper(self):
        data = self.package_metadata(); lock = wheel_lock(data, self.pin, tags=self.tags, environment=self.env)
        self.assertEqual(len(lock['packages']), 2); validate_lock(lock, data, self.pin, tags=self.tags, environment=self.env)
        lock['packages'][0]['sha256'] = 'b' * 64
        with self.assertRaises(PilotError): validate_lock(lock, data, self.pin, tags=self.tags, environment=self.env)

    def test_dependency_missing_incompatible_url_unknown_and_extra_rejected(self):
        self.package_metadata()
        for mutate in [lambda d: d.pop('requests'), lambda d: d['requests']['info'].update(version='2.0'), lambda d: d['osmium']['info'].update(requires_dist=['unknown']), lambda d: d['osmium']['info'].update(requires_dist=['requests[security]']), lambda d: d['requests']['urls'][0].update(url='https://evil.test/a.whl')]:
            data = self.package_metadata(); mutate(data)
            with self.assertRaises((PilotError, ValueError)): wheel_lock(data, self.pin, tags=self.tags, environment=self.env)

    def wheel(self, extra=None):
        path = self.root / ('wheel' + str(self.serial) + '.whl'); self.serial += 1
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('example-1.0.dist-info/METADATA', b'Name: example\nVersion: 1.0\n')
            z.writestr('example/__init__.py', b'value=1\n')
            if extra:
                name, data, mode = extra; info = zipfile.ZipInfo(name); info.external_attr = mode << 16; z.writestr(info, data)
        return path, {'name': 'example', 'version': '1.0', 'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_wheel_validation_and_tool_byte_cap(self):
        path, pin = self.wheel(); root = self.root / 'unpack'; result = unpack_wheel(path, pin, root, 1000)
        self.assertEqual(result['files'], 2)
        with self.assertRaises(PilotError): unpack_wheel(path, pin, self.root / 'small', 1)
        pin['sha256'] = '0' * 64
        with self.assertRaises(PilotError): unpack_wheel(path, pin, self.root / 'hash', 1000)

    def test_wheel_zip_traversal_symlink_duplicate_and_hook_rejected(self):
        for extra in [('../escape', b'x', 0), ('/absolute', b'x', 0), ('link', b'x', 0o120777), ('example/__init__.py', b'x', 0), ('hook.pth', b'import os', 0)]:
            path, pin = self.wheel(extra)
            with self.assertRaises(PilotError): unpack_wheel(path, pin, self.root / ('bad' + str(self.serial)), 1000)
        self.assertFalse((self.root / 'escape').exists())

    def test_captured_root_wheel_metadata_pin_and_future_recipe_validation(self):
        data = json.loads((PROPOSAL.parent / 'linux-metadata/pyosmium-json.bin').read_text()); pin = json.loads(PROPOSAL.read_text())['tools']
        Tag = __import__('pip._vendor.packaging.tags', fromlist=['Tag']).Tag
        with self.assertRaises(PilotError): wheel_lock({'osmium': data}, pin, tags=[Tag('cp313', 'cp313', 'manylinux_2_28_aarch64')], environment={'python_version': '3.13', 'python_full_version': '3.13.5', 'extra': '', 'sys_platform': 'linux'})
        # Missing dependencies never yields a partial executable lock.
        from prepare_osm_bulk import DEPENDENCIES
        plan = {'phase': 'metadata_only_dependency_lock', 'network': 'bridge', 'caps': {'attempts': 5, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0}, 'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536},
            'specs': [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 2097152, 'seconds': 20} for n in DEPENDENCIES], 'memoryBytes': 1073741824, 'tmpBytes': 67108864, 'imagePull': 'never', 'output': 'data/coarse-quality/us-osm-tool-lock-v2'}
        validate_plan(plan); plan['phase'] = 'pbf'
        with self.assertRaises(PilotError): validate_plan(plan)

    def test_external_readonly_inputs_count_against_working_storage(self):
        root = self.directory()
        state = extract(lambda: iter(objects()), self.proposal, root, source_identity=self.identity, reserved_input_bytes=33554432)
        self.assertEqual(state['status'], 'stopped'); self.assertIn('storage', state['error'])

    def test_http_normal_close_is_within_absolute_deadline(self):
        now = [0.]; r = Response()
        def close(): now[0] = 3.
        r.close = close
        m, _ = self.meter(r, clock=lambda: now[0], alarm=lambda _: nullcontext())
        with self.assertRaises(PilotError): m.fetch(0)
        self.assertEqual(m.events[0]['outcome'], 'failed')

    def test_metadata_resolver_completes_closed_lock_without_binary_requests(self):
        from prepare_osm_bulk import DEPENDENCIES
        data = self.package_metadata()
        for name in DEPENDENCIES[1:]:
            item = deepcopy(data['requests']); item['info']['name'] = name
            f = item['urls'][0]; f['filename'] = name.replace('-', '_') + '-1.0-py3-none-any.whl'
            f['url'] = 'https://files.pythonhosted.org/packages/aa/' + f['filename']; data[name] = item
        data['requests']['info']['requires_dist'] = [n + '>=1,<2' for n in DEPENDENCIES[1:]]
        specs = [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 2097152, 'seconds': 20} for n in DEPENDENCIES]
        caps = {'attempts': 5, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0}, 'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536}
        transport = Transport([Response(canonical(data[n])) for n in DEPENDENCIES]); root = self.directory()
        result = resolve(root, {'specs': specs, 'caps': caps}, {'tools': self.pin}, data['osmium'], transport=transport)
        self.assertEqual(result, 0); self.assertEqual(len(transport.calls), 5)
        self.assertEqual(len(json.loads((root / 'lock.json').read_text())['packages']), 6)
        self.assertEqual(json.loads((root / 'setup-state.json').read_text())['toolBinaryDownloads'], 0)
        transport = Transport([Response(status=502)]); root = self.directory()
        self.assertEqual(resolve(root, {'specs': specs, 'caps': caps}, {'tools': self.pin}, data['osmium'], transport=transport), 2)
        self.assertEqual(len(transport.calls), 1); self.assertFalse((root / 'lock.json').exists())
        self.assertEqual(sum(r['status'] == 'unmeasured_after_stop' for r in json.loads((root / 'setup-state.json').read_text())['plannedRequests']), 4)

    def test_launcher_refuses_unbound_recipe_before_docker_or_output(self):
        from prepare_osm_bulk import driver
        with patch('subprocess.run') as subprocess:
            with self.assertRaises(PilotError): driver(str(self.root / 'unbound.json'), '0' * 64, 'data/coarse-quality/us-osm-tool-lock-v2')
            subprocess.assert_not_called()

    def test_independent_sql_audit_detects_primary_lookup_bug(self):
        with patch('coarse_osm_bulk.Coordinates.points', return_value=[[10., 10.], [11., 11.]]): state, _ = self.run_extract()
        self.assertEqual(state['status'], 'stopped'); self.assertIn('Audit', state['error'])

    def test_unsupported_primitive_precision_rejected(self):
        prefix = pbf()[:-len(frame(b'OSMData', field(1, b'')))]
        for extra in [field(17, 1), field(18, 1), field(19, 1), field(17, 100) + field(17, 100)]:
            path = self.root / ('precision' + str(self.serial)); self.serial += 1
            path.write_bytes(prefix + frame(b'OSMData', field(1, b'') + extra))
            with self.assertRaises(PilotError): framing(path, self.proposal['proposedCaps'], STATE)

    def test_native_duplicate_tags_and_subsecond_time_are_not_flattened(self):
        stamp = datetime.datetime.fromisoformat('2026-10-20T00:00:00+00:00')
        obj = SimpleNamespace(type_str=lambda: 'n', id=1, version=1, timestamp=stamp, visible=True,
            tags=[SimpleNamespace(k='x', v='a'), SimpleNamespace(k='x', v='b')], location=SimpleNamespace(lon=1., lat=2.))
        with patch.dict(sys.modules, {'osmium': SimpleNamespace(FileProcessor=lambda _: iter([obj]))}):
            with self.assertRaises(PilotError): list(native_records('unused', 1000))
            obj.tags = []; obj.timestamp = stamp.replace(microsecond=1)
            with self.assertRaises(PilotError): list(native_records('unused', 1000))

    def test_meter_absolute_alarm_interrupts_blocking_connect(self):
        m, transport = self.meter(spec={'seconds': .03})
        def blocked(*_): time.sleep(1)
        transport.open = blocked
        with self.assertRaises(PilotError): m.fetch(0)
        self.assertEqual(len(m.events), 1); self.assertEqual(m.events[0]['bodyBytes'], 0)

    def test_single_record_and_normalized_wrapper_caps(self):
        for limit in (30, max(len(canonical(r)) for r in objects()) + 16):
            proposal = deepcopy(self.proposal); proposal['proposedCaps']['singleNormalizedElementBytes'] = limit
            state, root = self.run_extract(proposal=proposal); self.assertEqual(state['status'], 'stopped')
            if (root / 'elements.jsonl').exists():
                for line in (root / 'elements.jsonl').read_bytes().splitlines(): self.assertLessEqual(len(line) + 1, limit)

    def test_failed_projection_counter_scope_is_explicit(self):
        rows = objects(); rows[0]['version'] = 0
        state, _ = self.run_extract(rows)
        self.assertEqual(state['scanObjectVisits'], 1); self.assertTrue(state['rawDecodedObjectCountsMayBePartial'])

    def test_owned_launcher_oom_retains_partial_counters_and_cleans_up(self):
        import prepare_osm_bulk as launcher
        from prepare_osm_bulk import DEPENDENCIES
        repo = self.directory(); (repo / 'scripts').mkdir(); (repo / 'docs/evidence').mkdir(parents=True)
        (repo / 'data/coarse-quality').mkdir(parents=True)
        recipe = repo / 'docs/evidence/setup.json'
        plan = {'phase': 'metadata_only_dependency_lock', 'network': 'bridge', 'caps': {'attempts': 5, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0}, 'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536},
            'specs': [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 2097152, 'seconds': 20} for n in DEPENDENCIES], 'memoryBytes': 1073741824, 'tmpBytes': 67108864, 'imagePull': 'never', 'imageId': 'sha256:fixture', 'output': 'data/coarse-quality/us-osm-tool-lock-v2', 'mounts': {}, 'inputs': {}, 'workerFiles': {}}
        recipe.write_bytes(canonical(plan)); identity = 'a' * 64; calls = []
        def command(args, **kwargs):
            calls.append(args)
            if args[1] == 'create':
                self.assertIn('--pull=never', args); self.assertIn('--read-only', args); self.assertIn('--init', args)
                return SimpleNamespace(stdout=identity)
            if args[1] == 'inspect':
                return SimpleNamespace(stdout=json.dumps([{'Image': plan['imageId'], 'HostConfig': {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True}, 'State': {'OOMKilled': True, 'ExitCode': 137}}]))
            if args[1] == 'start': return SimpleNamespace(returncode=137)
            self.assertEqual(args, ['docker', 'rm', '-f', identity]); return SimpleNamespace(returncode=0)
        with patch.object(launcher, '__file__', str(repo / 'scripts/prepare_osm_bulk.py')), patch('subprocess.run', side_effect=command):
            self.assertEqual(launcher.driver(str(recipe), hashlib.sha256(recipe.read_bytes()).hexdigest(), plan['output']), 137)
        root = repo / plan['output']; self.assertTrue(json.loads((root / 'driver-stop.json').read_text())['hardStopCountersMayBePartial'])
        self.assertTrue(json.loads((root / 'cleanup.json').read_text())['removed'])


if __name__ == '__main__': unittest.main(verbosity=2)
