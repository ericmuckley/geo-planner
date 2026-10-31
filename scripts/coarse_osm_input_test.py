"""Synthetic native-OSM transport, cap, closure, identity and audit tests."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from coarse_osm_audit import audit, reference_batch
from coarse_osm_input import Budget, DirectHttps, STATE_RESERVE, absolute_timeout, capture, status_wait
from coarse_osm_records import batch, canonical, strict_json
from coarse_timing_input import PilotError
from run_osm_capture import load_queries


REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / 'docs/evidence/coarse-input-redesign-2026-10-26'
SNAPSHOT = '2026-10-21T00:00:00Z'
STATUS = b'Connected as: fixture\nCurrent time: 2026-10-26T00:00:00Z\nRate limit: 2\n2 slots available now.\n'


class Clock:
    def __init__(self): self.now = 0.
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


class Response:
    def __init__(self, raw, status=200, content_type='application/json', length='auto', headers=None, on_read=None, incomplete=None):
        self.raw, self.status, self.offset, self.closed = raw, status, 0, False
        self.headers = [('Content-Type', content_type)]
        if length == 'auto': length = len(raw)
        if length is not None: self.headers.append(('Content-Length', str(length)))
        if headers: self.headers.extend(headers)
        self.on_read, self.incomplete, self.reads = on_read, incomplete, 0
    def getheaders(self): return self.headers
    def read1(self, size):
        self.reads += 1
        if self.on_read: self.on_read()
        if self.incomplete is not None:
            value, self.incomplete = self.incomplete, None
            raise http.client.IncompleteRead(value, 1)
        result = self.raw[self.offset:self.offset + size]; self.offset += len(result)
        return result
    def close(self): self.closed = True


class Transport:
    def __init__(self, responses): self.responses, self.calls = list(responses), []
    def open(self, method, url, body, timeout):
        self.calls.append((method, url, body, timeout))
        if not self.responses: raise AssertionError('Unexpected extra HTTP attempt')
        response = self.responses.pop(0)
        if isinstance(response, Exception): raise response
        return response


def payload():
    common = {'version': 1, 'timestamp': '2026-10-20T00:00:00Z'}
    elements = [
        {'type': 'node', 'id': 1, **common, 'lat': 0., 'lon': -1., 'tags': {'barrier': 'gate'}},
        {'type': 'node', 'id': 2, **common, 'lat': 0., 'lon': 1.},
        {'type': 'way', 'id': 1, **common, 'nodes': [1, 2], 'tags': {'highway': 'primary', 'maxspeed': '55 mph',
            'maxspeed:conditional': '35 mph @ wet', 'access': 'yes', 'oneway': 'yes', 'layer': '0'}, 'user': 'optional fixture'},
        {'type': 'relation', 'id': 1, **common, 'tags': {'type': 'restriction', 'restriction:conditional': 'no_left_turn @ wet'},
            'members': [{'type': 'way', 'ref': 1, 'role': 'from'}, {'type': 'node', 'ref': 2, 'role': 'via'}, {'type': 'way', 'ref': 999, 'role': 'to'}]},
        {'type': 'count', 'id': 0, 'tags': {'nodes': '2', 'ways': '1', 'relations': '1', 'total': '4'}}]
    return {'version': .6, 'generator': 'Overpass API fixture', 'osm3s': {'timestamp_osm_base': '2026-10-26T00:00:00Z', 'copyright': 'OpenStreetMap fixture'}, 'elements': elements}


class OsmTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.serial = 0
        self.proposal = json.loads((DESIGN / 'proposal.json').read_text())
        manifest = json.loads((DESIGN / 'queries.json').read_text())
        self.queries = []
        for q in manifest['queries'][:3]:
            text = (REPO / q['path']).read_text()
            start, rest = text.split('way["highway"](', 1); _, tail = rest.split(')->.roads;', 1)
            text = start + 'way["highway"](-0.5,-0.5,0.5,0.5)->.roads;' + tail
            body = urlencode({'data': text}).encode()
            self.queries.append({**q, 'text': text, 'bbox': [-.5, -.5, .5, .5],
                'formBodySha256': hashlib.sha256(body).hexdigest(), 'formBodyBytes': len(body)})

    def run_capture(self, responses, count=1, change=None, clock=None, alarm=None):
        self.serial += 1; root = self.root / str(self.serial); root.mkdir()
        proposal = deepcopy(self.proposal)
        if change: change(proposal)
        clock = clock or Clock(); transport = Transport(responses)
        state = capture(proposal, self.queries[:count], root, transport=transport, clock=clock, sleep=clock.advance, alarm=alarm or (lambda _: nullcontext()))
        audited = audit(proposal, self.queries[:count], root)
        return state, audited, root, transport, proposal

    def success(self, count=1):
        return self.run_capture([item for _ in range(count) for item in (Response(STATUS), Response(canonical(payload())))], count)

    def stopped(self, response, change=None):
        result = self.run_capture([Response(STATUS), response], 3, change)
        state, audited, root, transport, _ = result
        self.assertEqual(state['status'], 'stopped'); self.assertFalse(audited['captureComplete'])
        self.assertEqual([w['status'] for w in state['windows']], ['incomplete_after_stop', 'unmeasured_after_stop', 'unmeasured_after_stop'])
        self.assertEqual(len(transport.calls), 2)
        return result

    def test_full_crossing_geometry_typed_ids_raw_scopes_and_external_relation(self):
        state, audited, root, transport, _ = self.success()
        self.assertTrue(audited['captureComplete']); self.assertEqual(audited['uniqueNormalizedElements'], 4)
        rows = [strict_json(line) for line in (root / 'elements.jsonl').read_bytes().splitlines()]
        self.assertEqual({(r['element']['type'], r['element']['id']) for r in rows}, {('node', 1), ('node', 2), ('way', 1), ('relation', 1)})
        way = next(r for r in rows if r['element']['type'] == 'way')
        self.assertEqual(way['element']['tags'], payload()['elements'][2]['tags']); self.assertNotIn('user', way['element'])
        report = json.loads((root / state['windows'][0]['reportPath']).read_text())
        self.assertEqual(report['externalRestrictionMemberCount'], 1); self.assertFalse(report['carAccessVerified'])
        self.assertFalse(state['sourceAdapterImplemented']); self.assertFalse(state['originalFeasibilityQualified'])
        self.assertEqual([c[0] for c in transport.calls], ['GET', 'POST'])

    def test_consistent_overlapping_windows_keep_one_native_identity(self):
        state, audited, _, _, _ = self.success(2)
        self.assertEqual(audited['httpAttempts'], 4); self.assertEqual(audited['validatedElementOccurrences'], 8)
        self.assertEqual(audited['uniqueNormalizedElements'], 4)
        self.assertEqual([w['newUniqueElements'] for w in state['windows']], [4, 0])

    def test_empty_query_result_is_complete_capture_without_source_admission(self):
        value = payload(); value['elements'] = [{'type': 'count', 'id': 0, 'tags': {'nodes': '0', 'ways': '0', 'relations': '0', 'total': '0'}}]
        state, audited, _, _, _ = self.run_capture([Response(STATUS), Response(canonical(value))])
        self.assertTrue(audited['captureComplete']); self.assertEqual(audited['uniqueNormalizedElements'], 0)
        self.assertFalse(state['originalFeasibilityQualified']); self.assertFalse(state['sourceAdapterImplemented'])

    def test_way_version_alone_does_not_identify_node_geometry(self):
        first = payload(); second = deepcopy(first); second['elements'][0].update(version=2, lon=-.9)
        a = batch(canonical(first), SNAPSHOT, self.queries[0]['bbox'], self.proposal['hardCaps'])
        b = batch(canonical(second), SNAPSHOT, self.queries[0]['bbox'], self.proposal['hardCaps'])
        wa = next(r for r in a['records'] if r['element']['type'] == 'way'); wb = next(r for r in b['records'] if r['element']['type'] == 'way')
        self.assertEqual(wa['elementSha256'], wb['elementSha256']); self.assertNotEqual(wa['geometryDependencySha256'], wb['geometryDependencySha256'])
        state, audited, _, transport, _ = self.run_capture([Response(STATUS), Response(canonical(first)), Response(STATUS), Response(canonical(second))], 3)
        self.assertIn('Conflicting duplicate', state['error']); self.assertEqual(audited['completedWindows'], 1)
        self.assertEqual(len(transport.calls), 4)

    def test_error_and_redirect_bodies_are_saved_without_retry(self):
        for status in (301, 429, 504):
            with self.subTest(status=status):
                response = Response(b'bounded error', status=status, headers=[('Location', 'https://unlisted.invalid/')])
                state, _, root, _, _ = self.stopped(response)
                self.assertEqual((root / state['http'][-1]['bodyFile']).read_bytes(), b'bounded error')
                self.assertTrue(response.closed)

    def test_reject_compressed_and_oversized_declared_body_before_reading(self):
        for response in [Response(b'not read', headers=[('Content-Encoding', 'gzip')]), Response(b'not read', length=20 * 1024 ** 2)]:
            state, _, root, _, _ = self.stopped(response)
            self.assertEqual(response.reads, 0); self.assertEqual((root / state['http'][-1]['bodyFile']).stat().st_size, 0)

    def test_stream_oversize_reads_one_metered_sentinel_byte(self):
        response = Response(b'abcdefghijklmnop', length=None)
        state, _, root, _, _ = self.stopped(response, lambda p: p['hardCaps'].update(queryAcceptedBodyBytes=8))
        self.assertEqual(state['http'][-1]['receivedBodyBytes'], 9)
        self.assertEqual((root / state['http'][-1]['bodyFile']).read_bytes(), b'abcdefghi')

    def test_exact_response_bound_with_verified_eof_passes(self):
        raw = canonical(payload())
        state, audited, _, _, _ = self.run_capture([Response(STATUS), Response(raw, length=None)], change=lambda p:p['hardCaps'].update(queryAcceptedBodyBytes=len(raw)))
        self.assertTrue(audited['captureComplete']); self.assertEqual(state['http'][-1]['receivedBodyBytes'], len(raw))

    def test_truncated_and_incomplete_read_partial_are_preserved(self):
        for response, expected in [(Response(b'prefix', length=20), b'prefix'), (Response(b'', length=20, incomplete=b'partial'), b'partial')]:
            state, _, root, _, _ = self.stopped(response)
            self.assertEqual((root / state['http'][-1]['bodyFile']).read_bytes(), expected)
            self.assertEqual(state['http'][-1]['receivedBodyBytes'], len(expected))

    def test_bad_http_framing_and_content_type_fail(self):
        for response in [Response(b'{}', headers=[('Content-Length', '2')]),
                Response(b'{}', headers=[('Transfer-Encoding', 'chunked')]), Response(b'{}', length='bogus'),
                Response(canonical(payload()), content_type='text/html')]:
            self.stopped(response)

    def test_invalid_json_remark_and_schema_stop_all_remaining_windows(self):
        bad = [b'<html>bad</html>', b'{"version":0.6', b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":1e999}']
        for extra in [{'remark': 'runtime timeout'}, {'error': 'failed'}, {'version': .7}]:
            bad.append(canonical({**payload(), **extra}))
        for raw in bad:
            with self.subTest(raw=raw[:60]): self.stopped(Response(raw))

    def test_final_count_must_be_unique_terminal_and_exact(self):
        samples = []
        for mutation in ['missing', 'duplicate', 'not_last', 'wrong_total', 'wrong_type', 'leading_zero']:
            p = payload()
            if mutation == 'missing': p['elements'].pop()
            elif mutation == 'duplicate': p['elements'].append(deepcopy(p['elements'][-1]))
            elif mutation == 'not_last': p['elements'][-2:] = p['elements'][-2:][::-1]
            elif mutation == 'wrong_total': p['elements'][-1]['tags']['total'] = '3'
            elif mutation == 'wrong_type': p['elements'][-1]['tags']['nodes'] = '1'
            else: p['elements'][-1]['tags']['total'] = '04'
            samples.append(p)
        for p in samples: self.stopped(Response(canonical(p)))

    def test_missing_nodes_duplicate_ids_and_unrelated_geometry_fail(self):
        for mutation in ['missing', 'duplicate', 'unrelated']:
            p = payload()
            if mutation == 'missing': p['elements'].pop(0); p['elements'][-1]['tags'].update(nodes='1', total='3')
            elif mutation == 'duplicate': p['elements'].insert(0, deepcopy(p['elements'][0])); p['elements'][-1]['tags'].update(nodes='3', total='5')
            else:
                p['elements'][0]['lon'] = 2.; p['elements'][1]['lon'] = 3.
            self.stopped(Response(canonical(p)))

    def test_source_timestamp_generator_and_typed_identity_fail_closed(self):
        for mutation in ['base', 'future', 'id_bool', 'version_bool', 'tag_type', 'deleted']:
            p = payload()
            if mutation == 'base': p['osm3s']['timestamp_osm_base'] = '2026-10-19T00:00:00Z'
            elif mutation == 'future': p['elements'][0]['timestamp'] = '2026-10-22T00:00:00Z'
            elif mutation == 'id_bool': p['elements'][0]['id'] = True
            elif mutation == 'version_bool': p['elements'][0]['version'] = True
            elif mutation == 'tag_type': p['elements'][2]['tags']['maxspeed'] = 55
            else: p['elements'][0]['visible'] = False
            self.stopped(Response(canonical(p)))
        changed = payload(); changed['generator'] += ' changed'
        state, audited, _, _, _ = self.run_capture([Response(STATUS), Response(canonical(payload())), Response(STATUS), Response(canonical(changed))], 2)
        self.assertIn('generator changed', state['error']); self.assertEqual(audited['completedWindows'], 1)

    def test_status_wait_is_bounded_and_honored_without_polling(self):
        busy = b'Current time: 2026-10-26T00:00:00Z\nRate limit: 2\nSlot available after: 2026-10-26T00:00:03Z, in 3 seconds.\n'
        state, audited, _, transport, _ = self.run_capture([Response(busy), Response(canonical(payload()))])
        self.assertTrue(audited['captureComplete']); self.assertEqual(state['windows'][0]['statusWaitSeconds'], 3.)
        self.assertEqual(len(transport.calls), 2)
        for raw in [b'html', busy.replace(b'00:00:03Z, in 3', b'00:00:31Z, in 31')]:
            state, audited, _, transport, _ = self.run_capture([Response(raw)], 3)
            self.assertFalse(audited['captureComplete']); self.assertEqual(len(transport.calls), 1)

    def test_fake_slow_read_absolute_and_global_deadlines(self):
        clock = Clock(); response = Response(STATUS, on_read=lambda:clock.advance(2))
        state, audited, _, _, _ = self.run_capture([response], clock=clock, change=lambda p:p['timeouts'].update(statusAbsoluteClientSeconds=1))
        self.assertIn('absolute deadline', state['error']); self.assertFalse(audited['captureComplete'])
        busy = b'Current time: 2026-10-26T00:00:00Z\nRate limit: 2\nSlot available after: 2026-10-26T00:00:03Z, in 3 seconds.\n'
        state, _, _, transport, _ = self.run_capture([Response(busy)], 3, change=lambda p:p['hardCaps'].update(wallSeconds=2))
        self.assertIn('Global deadline', state['error']); self.assertEqual(len(transport.calls), 1)

    def test_posix_timer_interrupts_a_blocking_body_read(self):
        response = Response(STATUS, on_read=lambda:time.sleep(.1))
        state, audited, _, _, _ = self.run_capture([response], change=lambda p:p['timeouts'].update(statusAbsoluteClientSeconds=.02), alarm=absolute_timeout)
        self.assertIn('absolute deadline', state['error']); self.assertFalse(audited['captureComplete']); self.assertTrue(response.closed)

    def test_connection_and_cleanup_are_inside_absolute_acceptance_deadline(self):
        clock = Clock()
        class SlowOpen(Transport):
            def open(self, *args): clock.advance(2); return super().open(*args)
        root = self.root / 'open'; root.mkdir(); proposal = deepcopy(self.proposal); proposal['timeouts']['statusAbsoluteClientSeconds'] = 1
        state = capture(proposal, self.queries[:1], root, transport=SlowOpen([Response(b'', length=0)]), clock=clock, alarm=lambda _:nullcontext())
        self.assertIn('absolute deadline', state['error']); self.assertFalse(audit(proposal, self.queries[:1], root)['captureComplete'])
        clock = Clock(); response = Response(STATUS)
        def close(): response.closed = True; clock.advance(2)
        response.close = close
        state, audited, _, _, _ = self.run_capture([response], clock=clock, change=lambda p:p['timeouts'].update(statusAbsoluteClientSeconds=1))
        self.assertIn('absolute deadline', state['error']); self.assertFalse(audited['captureComplete'])

    def test_connect_failure_preserves_empty_attempt_without_retry(self):
        state, audited, root, transport, _ = self.run_capture([OSError('fixture connect failure')], 3)
        self.assertEqual(len(transport.calls), 1); self.assertEqual(audited['receivedHttpBodyBytes'], 0)
        self.assertEqual((root / state['http'][0]['bodyFile']).read_bytes(), b'')
        self.assertEqual(state['http'][0]['outcome'], 'failed')

    def test_occurrence_limit_counts_repeated_window_elements(self):
        state, audited, _, _, _ = self.run_capture([Response(STATUS), Response(canonical(payload())), Response(STATUS), Response(canonical(payload()))], 2,
            change=lambda p:p['hardCaps'].update(elementOccurrencesAllWindows=6))
        self.assertIn('occurrence cap', state['error']); self.assertEqual(audited['validatedElementOccurrences'], 8)
        self.assertEqual(audited['uniqueNormalizedElements'], 4); self.assertFalse(audited['captureComplete'])

    def test_request_total_body_extract_and_element_limits(self):
        changes = [lambda p:p['hardCaps'].update(httpAttempts=1), lambda p:p['hardCaps'].update(totalHttpBodyBytes=1),
            lambda p:p['hardCaps'].update(normalizedExtractBytes=1), lambda p:p['hardCaps'].update(uniqueSourceElementsAllTypes=3),
            lambda p:p['hardCaps'].update(elementOccurrencesAllWindows=3), lambda p:p['hardCaps'].update(singleNormalizedElementBytes=32)]
        for change in changes:
            state, audited, _, transport, _ = self.run_capture([Response(STATUS), Response(canonical(payload()))], 3, change)
            self.assertFalse(audited['captureComplete']); self.assertEqual(state['status'], 'stopped'); self.assertLessEqual(len(transport.calls), 2)

    def test_partial_normalized_prefix_survives_extract_cap(self):
        reference = batch(canonical(payload()), SNAPSHOT, self.queries[0]['bbox'], self.proposal['hardCaps'])
        first = canonical({'firstWindowId': self.queries[0]['id'], **reference['records'][0]}) + b'\n'
        state, audited, root, _, _ = self.stopped(Response(canonical(payload())), lambda p:p['hardCaps'].update(normalizedExtractBytes=len(first)))
        self.assertEqual((root / 'elements.jsonl').read_bytes(), first); self.assertEqual(audited['uniqueNormalizedElements'], 1)
        self.assertIn('extract cap', state['error'])

    def test_working_storage_guard_and_output_reuse(self):
        state, audited, root, _, proposal = self.run_capture([Response(STATUS)], change=lambda p:p['hardCaps'].update(workingBytes=p['hardCaps']['tmpBytes'] + STATE_RESERVE))
        self.assertFalse(audited['captureComplete']); self.assertEqual(state['budget']['httpAttempts'], 0)
        with self.assertRaises(PilotError): capture(proposal, self.queries[:1], root, transport=Transport([]))
        b = Budget(self.proposal['hardCaps'], root)
        with self.assertRaises(PilotError): b.path('../outside')
        state, audited, root, _, _ = self.run_capture([Response(STATUS)], change=lambda p:p['hardCaps'].update(workingBytes=p['hardCaps']['tmpBytes'] + STATE_RESERVE + 1))
        self.assertFalse(audited['captureComplete']); self.assertEqual(state['http'][0]['receivedBodyBytes'], 1)
        self.assertEqual((root / state['http'][0]['bodyFile']).read_bytes(), STATUS[:1])

    def test_frozen_post_change_is_refused_before_query_io(self):
        self.queries[0]['text'] += ' changed'
        state, audited, _, transport, _ = self.run_capture([Response(STATUS)], 2)
        self.assertIn('Frozen request body', state['error']); self.assertEqual(len(transport.calls), 1); self.assertFalse(audited['captureComplete'])

    def test_native_https_does_not_use_env_auth_proxy_or_redirect_handlers(self):
        response = Response(b'fixed')
        class Connection:
            def __init__(self): self.calls = []; self.closed = False
            def request(self, *args, **kwargs): self.calls.append((args, kwargs))
            def getresponse(self): return response
            def close(self): self.closed = True
        connection = Connection()
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://dummy.invalid', 'HTTP_PROXY': 'https://dummy.invalid'}), patch('http.client.HTTPSConnection', return_value=connection) as factory:
            result = DirectHttps().open('GET', 'https://overpass-api.de/api/status', None, 2)
            factory.assert_called_once_with('overpass-api.de', 443, timeout=2)
            headers = connection.calls[0][1]['headers']
            self.assertNotIn('Authorization', headers); self.assertNotIn('Cookie', headers); self.assertEqual(headers['Accept-Encoding'], 'identity')
            result.close(); self.assertTrue(connection.closed)
            for url in ['http://overpass-api.de/api/status', 'https://other.invalid/api/status', 'https://user@overpass-api.de/api/status', 'https://overpass-api.de/api/status?x=1']:
                with self.assertRaises(PilotError): DirectHttps().open('GET', url, None, 2)

    def test_query_loader_binds_all_original_bounds_and_form_hashes(self):
        manifest = json.loads((DESIGN / 'queries.json').read_text())
        original = json.loads((REPO / self.proposal['windows']['sourceProposal']).read_text())
        paths = {q['id']: REPO / q['path'] for q in manifest['queries']}
        loaded = load_queries(self.proposal, manifest, paths, original); self.assertEqual(len(loaded), 21)
        changed = deepcopy(manifest); changed['queries'][0]['formBodySha256'] = 'wrong'
        with self.assertRaises(PilotError): load_queries(self.proposal, changed, paths, original)
        changed = deepcopy(manifest); changed['queries'][0]['bbox'][0] += .001
        with self.assertRaises(PilotError): load_queries(self.proposal, changed, paths, original)

    def test_reference_reconstruction_shares_no_primary_batch_or_normalizer(self):
        raw = canonical(payload()); expected = batch(raw, SNAPSHOT, self.queries[0]['bbox'], self.proposal['hardCaps'])
        with patch('coarse_osm_records.batch', side_effect=AssertionError('primary replay')), patch('coarse_osm_records.normalize', side_effect=AssertionError('primary replay')):
            self.assertEqual(reference_batch(raw, SNAPSHOT, self.queries[0]['bbox'], self.proposal['hardCaps']), expected)

    def test_audit_rejects_body_count_identity_wait_and_admission_tampering(self):
        for mutation in ('body', 'dependency', 'state_bytes', 'wait', 'snapshot', 'admission'):
            with self.subTest(mutation=mutation):
                state, _, root, _, proposal = self.success()
                if mutation == 'body':
                    path = root / state['http'][-1]['bodyFile']; path.write_bytes(path.read_bytes() + b' ')
                elif mutation == 'dependency':
                    path = root / 'elements.jsonl'; rows = [strict_json(line) for line in path.read_bytes().splitlines()]
                    next(r for r in rows if r['element']['type'] == 'way')['geometryDependencySha256'] = 'changed'
                    path.write_bytes(b''.join(canonical(r) + b'\n' for r in rows))
                else:
                    if mutation == 'state_bytes': state['budget']['receivedHttpBodyBytes'] += 1
                    elif mutation == 'wait': state['windows'][0]['statusWaitSeconds'] = 3.
                    elif mutation == 'snapshot': state['snapshotUtc'] = '2026-10-22T00:00:00Z'
                    else: state['originalFeasibilityQualified'] = True
                    (root / 'state.json').write_bytes(canonical(state))
                with self.assertRaises(PilotError): audit(proposal, self.queries[:1], root)


if __name__ == '__main__':
    unittest.main()
