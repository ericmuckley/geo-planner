"""Synthetic protocols, scoped rules and weighted geometry; no network or keys."""
from copy import deepcopy
import hashlib
import http.client
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from coarse_timing_input import Budget, Meter, NoRedirect, PilotError, RangeFile, canonical_etag, list_objects, usable_limit
from coarse_timing_parquet import MatchIndex, angle_degrees, clip_segment, decode_lines, source_spans


class Response:
    def __init__(self, body=b'abcd', status=200, headers=None, incomplete=False):
        self.body, self.position, self.status, self.closed, self.incomplete = body, 0, status, False, incomplete
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}

    def read(self, size):
        if self.incomplete:
            self.incomplete = False
            raise http.client.IncompleteRead(self.body[:2], 2)
        raw = self.body[self.position:self.position + size]
        self.position += len(raw)
        return raw

    def close(self):
        self.closed = True


class Opener:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def open(self, request, **kwargs):
        self.requests.append(request)
        return self.responses.pop(0)


class TimingInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.caps = {'wallSeconds': 10, 'httpRequests': 5, 'receivedHttpBodyBytes': 100,
                     'toolDownloadBodyBytesWithinTotal': 50, 'totalLocalWorkingBytes': 1024 ** 3}
        self.now = 0
        self.budget = Budget(self.caps, Path(self.temp.name), clock=lambda: self.now)

    def meter(self, *responses):
        opener = Opener(responses)
        events = []
        meter = Meter(self.budget, ['test.invalid'], opener=opener, record=lambda e: events.append(deepcopy(e)))
        return meter, opener, events

    def test_http_complete_body_is_counted_and_closed(self):
        response = Response()
        meter, opener, events = self.meter(response)
        self.assertEqual(meter.get('https://test.invalid/a', limit=4)[0], b'abcd')
        self.assertEqual(self.budget.bytes, 4)
        self.assertEqual(self.budget.requests, 1)
        self.assertTrue(response.closed)
        self.assertEqual(events[-1]['outcome'], 'complete')

    def test_url_credentials_host_and_plain_http_are_rejected_before_io(self):
        meter, opener, _ = self.meter()
        for url in ['http://test.invalid/a', 'https://user:secret@test.invalid/a', 'https://else.invalid/a', 'https://test.invalid:123/a']:
            with self.subTest(url=url), self.assertRaises(PilotError):
                meter.get(url, limit=4)
        self.assertEqual(opener.requests, [])
        self.assertEqual(self.budget.requests, 0)

    def test_oversized_body_fails_before_read_and_cannot_retry(self):
        response = Response(b'12345')
        meter, opener, events = self.meter(response)
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=4)
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=4)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(self.budget.bytes, 0)
        self.assertTrue(response.closed)
        self.assertEqual(events[-1]['outcome'], 'failed')

    def test_error_and_redirect_bodies_count_without_following(self):
        meter, opener, events = self.meter(Response(b'err', status=302, headers={'Location': 'https://test.invalid/b'}))
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=4)
        self.assertEqual(self.budget.bytes, 3)
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(events[-1]['status'], 302)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://test.invalid/b'))

    def test_truncation_including_exception_partial_bytes_counts_and_stops(self):
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete):
                self.budget = Budget(self.caps, Path(self.temp.name))
                response = Response(b'ab', headers={'Content-Length': '4'}, incomplete=incomplete)
                meter, _, _ = self.meter(response)
                with self.assertRaises(PilotError):
                    meter.get('https://test.invalid/a', limit=4)
                self.assertEqual(self.budget.bytes, 2)
                self.assertTrue(self.budget.stopped)

    def test_failed_response_body_and_checksum_reach_preservation_sink(self):
        saved = []
        meter = Meter(self.budget, ['test.invalid'], opener=Opener([Response(b'not found', status=404)]),
                      save_body=lambda raw, event: saved.append((raw, deepcopy(event))))
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=100)
        self.assertEqual(saved[0][0], b'not found')
        self.assertEqual(saved[0][1]['bodySha256'], hashlib.sha256(b'not found').hexdigest())
        self.assertEqual(self.budget.bytes, 9)

    def test_total_and_tool_byte_caps_precede_body_reads(self):
        self.caps['receivedHttpBodyBytes'] = 3
        meter, _, _ = self.meter(Response())
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=4)
        self.assertEqual(self.budget.bytes, 0)
        self.budget = Budget({**self.caps, 'receivedHttpBodyBytes': 100, 'toolDownloadBodyBytesWithinTotal': 3}, self.temp.name)
        meter, _, _ = self.meter(Response())
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=4, tool=True)
        self.assertEqual(self.budget.tool_bytes, 0)

    def test_unknown_length_stops_at_cap_without_extra_read(self):
        response = Response(b'123456')
        del response.headers['Content-Length']
        self.caps['receivedHttpBodyBytes'] = 4
        meter, _, _ = self.meter(response)
        with self.assertRaises(PilotError):
            meter.get('https://test.invalid/a', limit=10)
        self.assertEqual(self.budget.bytes, 4)
        self.assertEqual(response.position, 4)

    def test_request_and_wall_guards(self):
        self.caps['httpRequests'] = 1
        self.budget.request()
        with self.assertRaises(PilotError):
            self.budget.request()
        self.budget = Budget(self.caps, self.temp.name, clock=lambda: self.now)
        self.now = 11
        with self.assertRaises(PilotError):
            self.budget.request()

    def test_output_and_partial_extract_caps_preserve_previous_bytes(self):
        self.budget.write('a.json', b'{}')
        with self.assertRaises(PilotError):
            self.budget.write('a.json', b'changed')
        with self.assertRaises(PilotError):
            self.budget.write('../escape', b'x')
        self.budget.append('data.jsonl', b'abc', 4)
        with self.assertRaises(PilotError):
            self.budget.append('data.jsonl', b'de', 4)
        self.assertEqual(Path(self.temp.name, 'data.jsonl').read_bytes(), b'abc')
        self.caps['totalLocalWorkingBytes'] = 128 * 1024 ** 2
        with self.assertRaises(PilotError):
            self.budget.write('too-large', b'x')

    def test_range_seek_cache_and_identity_headers(self):
        response = Response(b'hi', status=206, headers={'ETag': '"e"', 'Content-Range': 'bytes 7-8/10'})
        meter, opener, _ = self.meter(response)
        with RangeFile(meter, {'url': 'https://test.invalid/a', 'bytes': 10, 'etag': '"e"'}) as file:
            file.seek(-3, 2)
            self.assertEqual(file.read(2), b'hi')
            file.seek(7)
            self.assertEqual(file.read(2), b'hi')
            self.assertEqual(len(opener.requests), 1)
            self.assertEqual(opener.requests[0].get_header('If-match'), '"e"')
            with self.assertRaises(PilotError):
                file.seek(-1)
        self.assertEqual(file.cached_bytes, 0)

    def test_range_ignored_or_changed_identity_never_returns_data(self):
        for status, tag, span in [(200, '"e"', 'bytes 0-3/10'), (206, '"changed"', 'bytes 0-3/10'), (206, '"e"', 'bytes 1-4/10')]:
            self.budget = Budget(self.caps, self.temp.name)
            meter, _, _ = self.meter(Response(status=status, headers={'ETag': tag, 'Content-Range': span}))
            with RangeFile(meter, {'url': 'https://test.invalid/a', 'bytes': 10, 'etag': '"e"'}) as file:
                with self.assertRaises(PilotError):
                    file.read(4)

    def test_empty_or_wrong_release_listing_stops(self):
        class Listing:
            def __init__(self, raw): self.raw = raw
            def get(self, *args, **kwargs): return self.raw, {}
        source = {'dataRoot': 'https://overturemapswestus2.blob.core.windows.net/release/frozen/theme=transportation/type=segment/'}
        with self.assertRaises(PilotError):
            list_objects(Listing(b'<EnumerationResults><Blobs/></EnumerationResults>'), source)
        raw = b'<EnumerationResults><Blobs><Blob><Name>other/x.parquet</Name></Blob></Blobs></EnumerationResults>'
        with self.assertRaises(PilotError):
            list_objects(Listing(raw), source)

    def test_azure_manifest_etags_and_continuation(self):
        prefix = 'frozen/theme=transportation/type=segment/'
        raw = ('<EnumerationResults><Blobs><Blob><Name>' + prefix + 'a.parquet</Name><Properties><Content-Length>100</Content-Length><Etag>0x123</Etag></Properties></Blob></Blobs></EnumerationResults>').encode()
        class Listing:
            def get(self, *args, **kwargs): return raw, {}
        records = list_objects(Listing(), {'dataRoot': 'https://overturemapswestus2.blob.core.windows.net/release/' + prefix})
        self.assertEqual(records[0]['etag'], '"0x123"')
        self.assertEqual(canonical_etag('"0x123"'), canonical_etag('0x123'))
        for bad in [None, 'W/"weak"', 'bad\nvalue']:
            with self.assertRaises(PilotError): canonical_etag(bad)

    def test_independent_watchdog_terminates_its_own_worker(self):
        program = 'from coarse_timing_input import start_watchdog; import time; start_watchdog(.05); time.sleep(5)'
        result = subprocess.run([sys.executable, '-B', '-c', program], cwd=Path(__file__).parent,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(result.returncode, -9)


def road(rules=None, **extra):
    return {'subtype': 'road', 'class': 'primary', 'speed_limits': rules, **extra}


class RuleAndGeometryTests(unittest.TestCase):
    def test_units_bidirectional_values_and_no_mutation(self):
        row = road([{'max_speed': {'value': 50, 'unit': 'mph'}}])
        before = deepcopy(row)
        self.assertAlmostEqual(usable_limit(row)['kmh'], 80.4672)
        self.assertEqual(row, before)
        row = road([{'max_speed': {'value': 70, 'unit': 'km/h'}, 'when': {'heading': h}} for h in ['forward', 'backward']])
        self.assertEqual(usable_limit(row), {'status': 'usable', 'kmh': 70})

    def test_all_unsupported_scopes_stay_explicit(self):
        base = {'max_speed': {'value': 70, 'unit': 'km/h'}}
        cases = [([], 'missing'), ({}, 'malformed'), ([{'min_speed': {'value': 20, 'unit': 'km/h'}}], 'no_explicit_maximum'), ([{**base, 'between': [.2, .8]}], 'partial_scope'),
                 ([{**base, 'is_max_speed_variable': True}], 'variable'),
                 ([{**base, 'when': {'during': 'Mo-Fr'}}], 'conditional'),
                 ([{**base, 'when': {'heading': 'forward'}}], 'directional'),
                 ([{**base, 'max_speed': {'value': 70, 'unit': 'knots'}}], 'unsupported_unit'),
                 ([{**base, 'max_speed': {'value': True, 'unit': 'km/h'}}], 'malformed'),
                 ([{**base, 'max_speed': {'value': float('nan'), 'unit': 'km/h'}}], 'malformed')]
        for rules, status in cases:
            with self.subTest(status=status):
                self.assertEqual(usable_limit(road(rules))['status'], status)
        self.assertEqual(usable_limit(road([base], access_restrictions=[{'access_type': 'denied'}]))['status'], 'access_scoped_or_restricted')
        self.assertEqual(usable_limit(road([base], **{'class': 'footway'}))['status'], 'unsupported_road_role')

    def test_conflicting_limits_are_not_flattened(self):
        rules = [{'max_speed': {'value': speed, 'unit': 'km/h'}} for speed in [50, 70]]
        self.assertEqual(usable_limit(road(rules))['status'], 'conflicting')
        rules[0]['when'] = {'heading': 'forward'}
        rules[1]['when'] = {'heading': 'backward'}
        self.assertEqual(usable_limit(road(rules))['status'], 'directional')

    def test_wkb_parts_never_gain_joining_segments(self):
        line = lambda a, b: struct.pack('<BIIdddd', 1, 2, 2, *a, *b)
        first, second = line([0, 0], [1, 0]), line([5, 0], [6, 0])
        raw = struct.pack('<BII', 1, 5, 2) + first + second
        self.assertEqual(decode_lines(raw), [[[0., 0.], [1., 0.]], [[5., 0.], [6., 0.]]])
        for invalid in [raw[:-1], raw + b'x', struct.pack('<BII', 1, 2, 300000)]:
            with self.assertRaises(PilotError): decode_lines(invalid)

    def test_clipping_and_undirected_tangents(self):
        self.assertEqual(clip_segment([-1, 0], [2, 0], [0, -1, 1, 1]), (1 / 3, 2 / 3))
        self.assertIsNone(clip_segment([-1, 2], [2, 2], [0, -1, 1, 1]))
        self.assertAlmostEqual(angle_degrees([0, 0], [1, 0], [1, 0], [0, 0]), 0)
        self.assertAlmostEqual(angle_degrees([0, 0], [1, 0], [.5, -1], [.5, 1]), 90)

    def test_original_source_weights_survive_clipping(self):
        data = {'nodeCoordinates': [0, 0, .01, 0], 'arcFrom': [0], 'arcTo': [1], 'arcRoadKm': [99],
                'arcInteriorOffsets': [0, 0], 'arcByteOffsets': [0, 0], 'geometryBytes': b'', 'interiorSourceKm': [],
                'cellIds': [10], 'cellArcOffsets': [0, 1], 'cellArcs': [0]}
        result = source_spans(data, {'bounds': [0, -.01, .1, .1], 'step': .01, 'width': 10, 'height': 10}, [.002, -.01, .008, .01])
        self.assertAlmostEqual(result[0][1][0][2], 59.4)

    def test_unique_partial_and_parallel_matches(self):
        row = {'id': 'a', 'version': 1, 'class': 'primary', '_lines': [[[0, 0], [.01, 0]]], '_limit': {'status': 'usable', 'kmh': 80}}
        spans = [([0, 0], [.01, 0], 99)]
        box = [-.01, -.01, .02, .01]
        self.assertAlmostEqual(MatchIndex([row], box).match(spans)['usableKm'], 99)
        parallel = {**row, 'id': 'b', '_lines': [[[0, .0001], [.01, .0001]]]}
        self.assertEqual(MatchIndex([row, parallel], box).match(spans)['status'], 'ambiguous')
        partial = {**row, '_lines': [[[0, 0], [.004, 0]]]}
        self.assertEqual(MatchIndex([partial], box).match(spans)['status'], 'unmatched')
        unsupported = {**row, '_limit': {'status': 'partial_scope', 'kmh': None}}
        self.assertEqual(MatchIndex([unsupported], box).match(spans)['usableKm'], 0)


if __name__ == '__main__':
    unittest.main()
