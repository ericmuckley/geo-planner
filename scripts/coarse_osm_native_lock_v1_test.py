"""Offline OCI/Git protocol and resource controls; never opens a real socket."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from coarse_osm_native_lock_v1 import (CAPS, CONFIG_TYPES, INDEX_TYPES, LAYER_TYPES, MANIFEST_TYPES,
    Metadata, ROOT_URL, SOURCES, SCOPE, endpoint, resolve, verify_saved)
from coarse_timing_input import PilotError, json_bytes


def encoded(value): return json_bytes(value)
def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()


class Reply:
    def __init__(self, value=b'', status=200, headers=(), *, length=True, partial=None):
        self.body = value if isinstance(value, bytes) else encoded(value)
        self.status, self.closed, self.partial = status, False, partial
        self.headers = ([('Content-Length', str(len(self.body)))] if length else []) + list(headers)
        self.stream = io.BytesIO(self.body)
    def read1(self, size):
        if self.partial is not None:
            value, self.partial = self.partial, None
            raise http.client.IncompleteRead(value, 5)
        return self.stream.read(size)
    def close(self): self.closed = True; self.stream.close()


class Transport:
    def __init__(self, replies): self.replies, self.calls = list(replies), []
    def open(self, url, kind, headers, seconds):
        self.calls.append((url, kind, headers))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception): raise reply
        return reply


def image_replies(*, index=False, auth=False, config_change=None, manifest_change=None, redirect=False):
    cfg = {'os': 'linux', 'architecture': 'arm64', 'rootfs': {'type': 'layers', 'diff_ids': ['sha256:' + 'b' * 64]}}
    if config_change: config_change(cfg)
    raw = encoded(cfg)
    manifest = {'schemaVersion': 2, 'mediaType': sorted(MANIFEST_TYPES)[0],
        'config': {'mediaType': sorted(CONFIG_TYPES)[0], 'digest': digest(raw), 'size': len(raw)},
        'layers': [{'mediaType': sorted(LAYER_TYPES)[0], 'digest': 'sha256:' + 'a' * 64, 'size': 1000}]}
    if manifest_change: manifest_change(manifest)
    body = encoded(manifest)
    replies = []
    if auth:
        challenge = f'Bearer realm="https://quay.io/v2/auth",service="quay.io",scope="{SCOPE}"'
        replies += [Reply(status=401, headers=[('WWW-Authenticate', challenge)]), Reply({'token': 'opaque-test-token-never-store'})]
    if index:
        desc = {'mediaType': manifest['mediaType'], 'digest': digest(body), 'size': len(body), 'platform': {'os': 'linux', 'architecture': 'arm64', 'variant': 'v8'}}
        root = encoded({'schemaVersion': 2, 'mediaType': sorted(INDEX_TYPES)[0], 'manifests': [desc]})
        replies.append(Reply(root, headers=[('Docker-Content-Digest', digest(root))]))
    replies.append(Reply(body, headers=[('Docker-Content-Digest', digest(body))]))
    replies.append(Reply(b'', status=302, headers=[('Location', 'https://cdn.quay.io/config')]) if redirect else Reply(raw))
    return replies


def source_replies(repo, tag, *, annotated=False, tree_change=None):
    commit, tree_id, tag_id = '1' * 40, '2' * 40, '3' * 40
    prefix = 'osmium' if repo == SOURCES[0][0] else 'protozero'
    tree = {'sha': tree_id, 'truncated': False, 'tree': [
        {'path': 'include', 'mode': '040000', 'type': 'tree', 'sha': '4' * 40},
        {'path': 'include/' + prefix, 'mode': '040000', 'type': 'tree', 'sha': '5' * 40},
        {'path': 'include/' + prefix + '/header.hpp', 'mode': '100644', 'type': 'blob', 'size': 9, 'sha': '6' * 40},
        {'path': 'LICENSE', 'mode': '100644', 'type': 'blob', 'size': 5, 'sha': '7' * 40},
        {'path': 'unused-submodule', 'mode': '160000', 'type': 'commit', 'sha': '8' * 40}]}
    if tree_change: tree_change(tree)
    replies = [Reply({'ref': 'refs/tags/' + tag, 'object': {'type': 'tag' if annotated else 'commit', 'sha': tag_id if annotated else commit}})]
    if annotated:
        replies.append(Reply({'sha': tag_id, 'object': {'type': 'commit', 'sha': commit}}))
    return replies + [Reply({'sha': commit, 'tree': {'sha': tree_id}}), Reply(tree)]


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root, self.number = Path(temp.name), 0

    def directory(self):
        self.number += 1
        p = self.root / str(self.number); p.mkdir(); return p

    def run_lock(self, replies, **kwargs):
        root, transport = self.directory(), Transport(replies)
        result = resolve(root, transport=transport, alarm=lambda s: nullcontext(), **kwargs)
        return result, root, transport

    def success(self, **kwargs):
        return image_replies(**kwargs) + [reply for repo, tag in SOURCES for reply in source_replies(repo, tag, annotated=True)]

    def test_complete_multiarch_and_single_manifest_locks(self):
        for indexed in (False, True):
            code, root, transport = self.run_lock(self.success(index=indexed))
            self.assertEqual(code, 0, (root / 'result.json').read_text())
            lock = json.loads((root / 'lock.json').read_text())
            self.assertEqual(lock['image']['platform'], 'linux/arm64')
            self.assertEqual(len(lock['sources']), 2)
            self.assertTrue(all(len(s['commit']) == len(s['tree']) == 40 for s in lock['sources']))
            self.assertTrue(all(s['archiveSha256'] is None for s in lock['sources']))
            self.assertTrue(verify_saved(root)['completeLockReplayed'])
            self.assertTrue(all('/layers/' not in url for url, _, _ in transport.calls))

    def test_anonymous_auth_is_bounded_redacted_and_not_forwarded(self):
        code, root, transport = self.run_lock(self.success(auth=True))
        self.assertEqual(code, 0)
        for url, kind, headers in transport.calls:
            if kind == 'git' or kind == 'auth': self.assertNotIn('Authorization', headers)
        self.assertFalse(any(b'opaque-test-token-never-store' in p.read_bytes() for p in root.rglob('*') if p.is_file()))
        auth = next(e for e in json.loads((root / 'http/ledger.json').read_text())['events'] if e['kind'] == 'auth')
        self.assertIsNone(auth['bodyFile'])
        self.assertGreater(auth['bodyBytes'], 0)
        self.assertTrue(verify_saved(root)['completeLockReplayed'])
        replies = self.success(auth=True)
        replies[0].headers = [('Content-Length', '0'), ('WWW-Authenticate', 'Bearer realm="https://quay.io/v2/auth",service="quay.io"')]
        self.assertEqual(self.run_lock(replies)[0], 0)

    def test_bad_registry_auth_scope_or_body_stops_without_retry(self):
        for challenge in ['Basic realm="quay.io"', f'Bearer realm="https://other.test/v2/auth",service="quay.io",scope="{SCOPE}"',
                          'Bearer realm="https://quay.io/v2/auth",service="quay.io",scope="repository:other:pull"']:
            code, root, transport = self.run_lock([Reply(status=401, headers=[('WWW-Authenticate', challenge)])])
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 1)
        replies = self.success(auth=True); replies[1] = Reply({'token': 'bad\nvalue'})
        code, _, transport = self.run_lock(replies)
        self.assertEqual(code, 2)
        self.assertEqual(len(transport.calls), 2)

    def test_redirect_and_http_errors_preserve_the_stop(self):
        for replies in [[Reply(b'no', status=403)], image_replies(redirect=True)]:
            code, root, transport = self.run_lock(replies)
            self.assertEqual(code, 2)
            self.assertFalse((root / 'lock.json').exists())
            self.assertEqual(len(transport.calls), len(replies))
            self.assertFalse(verify_saved(root)['completeLockReplayed'])

    def test_digest_size_platform_and_layer_closure_refusals(self):
        variants = [image_replies(config_change=lambda c: c.update(architecture='amd64')),
            image_replies(config_change=lambda c: c['rootfs'].update(diff_ids=[])),
            image_replies(manifest_change=lambda m: m['config'].update(size=m['config']['size'] + 1)),
            image_replies(manifest_change=lambda m: m['layers'][0].update(size=2147483648)),
            image_replies(manifest_change=lambda m: m['layers'][0].update(mediaType='unknown'))]
        wrong = image_replies(); wrong[0].headers[-1] = ('Docker-Content-Digest', 'sha256:' + 'f' * 64); variants.append(wrong)
        for replies in variants:
            code, root, _ = self.run_lock(replies)
            self.assertEqual(code, 2)
            self.assertFalse((root / 'lock.json').exists())

    def test_ambiguous_or_missing_arm64_descriptor_rejected(self):
        for count in (0, 2):
            replies = image_replies(index=True)
            root = json.loads(replies[0].body)
            root['manifests'] = root['manifests'] * count
            body = encoded(root); replies[0] = Reply(body, headers=[('Docker-Content-Digest', digest(body))])
            code, _, transport = self.run_lock(replies)
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 1)

    def test_source_lightweight_tag_and_selected_regular_files(self):
        code, root, _ = self.run_lock(image_replies() + [r for repo, tag in SOURCES for r in source_replies(repo, tag)])
        self.assertEqual(code, 0)
        source = json.loads((root / 'source-1-lock.json').read_text())
        self.assertEqual(source['annotatedTags'], [])
        self.assertEqual(source['selectedBytes'], 14)
        self.assertEqual(len(source['entries']), 5)

    def test_source_tree_paths_modes_sizes_truncation_and_identity(self):
        def path(value): return lambda t: t['tree'][2].update(path=value)
        mutations = [path('../escape'), path('/absolute'), path('include\\bad'), path('include//bad'),
            path('include/not-a-parent/a.hpp'), path('LICENSE'),
            lambda t: t.update(truncated=True), lambda t: t.update(sha='f' * 40),
            lambda t: t['tree'][2].update(size=-1), lambda t: t['tree'][2].update(size=True),
            lambda t: t['tree'][2].update(mode='120000'), lambda t: t['tree'][2].update(sha='g' * 40)]
        for mutate in mutations:
            code, root, _ = self.run_lock(image_replies() + source_replies(*SOURCES[0], tree_change=mutate))
            self.assertEqual(code, 2)
            self.assertTrue((root / 'image-lock.json').exists())
            self.assertFalse((root / 'source-1-lock.json').exists())

    def test_tag_cycle_wrong_commit_and_wrong_ref(self):
        variants = []
        rows = source_replies(*SOURCES[0], annotated=True)
        rows[1] = Reply({'sha': '3' * 40, 'object': {'type': 'tag', 'sha': '3' * 40}}); variants.append(rows)
        rows = source_replies(*SOURCES[0]); rows[1] = Reply({'sha': 'f' * 40, 'tree': {'sha': '2' * 40}}); variants.append(rows)
        rows = source_replies(*SOURCES[0]); rows[0] = Reply({'ref': 'refs/tags/other', 'object': {'type': 'commit', 'sha': '1' * 40}}); variants.append(rows)
        for rows in variants:
            code, _, _ = self.run_lock(image_replies() + rows)
            self.assertEqual(code, 2)

    def test_partial_first_source_is_preserved_if_second_fails(self):
        replies = image_replies() + source_replies(*SOURCES[0]) + [Reply(status=404)]
        code, root, _ = self.run_lock(replies)
        self.assertEqual(code, 2)
        self.assertTrue((root / 'source-1-lock.json').exists())
        self.assertFalse((root / 'lock.json').exists())
        self.assertEqual(json.loads((root / 'result.json').read_text())['sources'][SOURCES[1][0]], 'unmeasured')

    def test_endpoint_policy_and_cross_host_authorization(self):
        for url, kind in [('https://evil.test/x', 'git'), ('https://quay.io/v2/other/manifests/latest', 'registry'),
            ('https://api.github.com/repos/osmcode/libosmium/zipball/x', 'git'),
            ('https://quay.io:444/v2/auth?service=quay.io', 'auth'), (ROOT_URL + '?x=1', 'registry')]:
            with self.assertRaises(PilotError): endpoint(url, kind)
        meter = Metadata(self.directory() / 'http', transport=Transport([]))
        with self.assertRaises(PilotError):
            meter.fetch('https://api.github.com/repos/osmcode/libosmium/git/ref/tags/v2.23.1', 'git', bearer='secret')
        self.assertEqual(meter.events, [])

    def test_declared_streamed_aggregate_and_attempt_quotas(self):
        for changes in [{'eachBytes': 10}, {'totalBytes': 10}, {'attempts': 1}]:
            code, root, _ = self.run_lock(self.success(), caps=dict(CAPS, **changes))
            self.assertEqual(code, 2)
            ledger = json.loads((root / 'http/ledger.json').read_text())
            self.assertLessEqual(ledger['receivedBodyBytes'], dict(CAPS, **changes)['totalBytes'])
        reply = Reply(b'123456', length=False)
        meter = Metadata(self.directory() / 'http', transport=Transport([reply]), caps=dict(CAPS, eachBytes=4))
        with self.assertRaises(PilotError): meter.fetch(ROOT_URL, 'registry')
        self.assertEqual(meter.bytes, 4)
        self.assertTrue(reply.closed)

    def test_truncated_and_incomplete_read_prefix_accounting(self):
        for reply in [Reply(b'ab', headers=[('Content-Length', '5')], length=False), Reply(b'', headers=[('Content-Length', '5')], length=False, partial=b'ab')]:
            meter = Metadata(self.directory() / 'http', transport=Transport([reply]), alarm=lambda s: nullcontext())
            with self.assertRaises(Exception): meter.fetch(ROOT_URL, 'registry')
            self.assertEqual(meter.bytes, 2)
            self.assertEqual((meter.root / '001.bin').read_bytes(), b'ab')
            self.assertTrue(meter.stopped)
            with self.assertRaises(PilotError): meter.fetch(ROOT_URL, 'registry')
            self.assertEqual(len(meter.events), 1)

    def test_header_compression_duplicates_and_transport_failure(self):
        for reply in [Reply(b'{}', headers=[('Content-Encoding', 'gzip')]), Reply(b'{}', headers=[('Content-Length', '2')]), TimeoutError('timed out')]:
            code, root, transport = self.run_lock([reply])
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 1)
            self.assertEqual(json.loads((root / 'result.json').read_text())['requests'], 1)

    def test_deadline_and_working_storage_before_request(self):
        clock = [0]
        meter = Metadata(self.directory() / 'http', transport=Transport([]), clock=lambda: clock[0])
        clock[0] = CAPS['workerSeconds']
        with self.assertRaises(PilotError): meter.fetch(ROOT_URL, 'registry')
        self.assertEqual(meter.events, [])
        meter = Metadata(self.directory() / 'http', transport=Transport([]), caps=dict(CAPS, workingBytes=1))
        with self.assertRaises(PilotError): meter.fetch(ROOT_URL, 'registry')

    def test_driver_isolation_network_and_writable_input_refused(self):
        from prepare_osm_native_lock_v1 import IMAGE, limits, check_isolation
        for network in ('none', 'bridge'):
            obj = {'Image': IMAGE, 'HostConfig': dict(limits(network), Ulimits=[{'Name': 'core', 'Soft': 0, 'Hard': 0}, {'Name': 'fsize', 'Soft': 67108864, 'Hard': 67108864}]),
                'Mounts': [{'Destination': '/work', 'RW': True}, {'Destination': '/code/script.py', 'RW': False}]}
            check_isolation(obj, network)
            with self.assertRaises(PilotError): check_isolation(obj, 'bridge' if network == 'none' else 'none')
            obj['Mounts'][1]['RW'] = True
            with self.assertRaises(PilotError): check_isolation(obj, network)

    def test_driver_frozen_plan_rejects_drift_and_source_mounts(self):
        from prepare_osm_native_lock_v1 import IMAGE, validate
        plan = {'phase': 'native_build_metadata_lock_v1', 'caps': deepcopy(CAPS), 'imageId': IMAGE, 'imagePull': 'never',
            'output': 'data/coarse-quality/us-osm-native-lock-v1', 'rootUrl': ROOT_URL, 'sources': [list(s) for s in SOURCES],
            'phases': {'controls': 'none', 'acquire': 'bridge'}, 'mounts': {'scripts/a.py': '/code/a.py'},
            'inputs': {'scripts/a.py': 'hash'}, 'workerFiles': {'/code/a.py': 'hash'}}
        validate(plan)
        for change in ('caps', 'selector', 'source', 'path', 'binding'):
            bad = deepcopy(plan)
            if change == 'caps': bad['caps']['attempts'] += 1
            elif change == 'selector': bad['sources'][0][1] = 'other'
            elif change in ('source', 'path'):
                bad['mounts'] = {'data/source.pbf' if change == 'source' else 'scripts/../data/a.py': '/code/a.py'}
            else: bad['workerFiles']['/code/a.py'] = 'different'
            with self.assertRaises((PilotError, KeyError)): validate(bad)

    def test_driver_error_exit_capture_and_create_timeout_discovery(self):
        from prepare_osm_native_lock_v1 import IMAGE, settle_error
        for running in (False, True):
            obj = {'Id': 'a' * 64, 'Image': IMAGE, 'Config': {'Labels': {'geo-planner.stream-owner': 'owner'}}, 'State': {'Running': running, 'ExitCode': 0, 'OOMKilled': False}}
            calls = []
            def call(args):
                calls.append(args)
                if args[1] == 'kill':
                    obj['State'].update(Running=False, ExitCode=137)
                    return subprocess.CompletedProcess(args, 0, '', '')
                return subprocess.CompletedProcess(args, 0, json.dumps([obj]), '')
            root = self.directory()
            settle_error(call, None, 'created-name', 'owner', root, -9)
            self.assertEqual(calls[0], ['docker', 'inspect', 'created-name'])
            state = json.loads((root / 'container-error-final.json').read_text())
            self.assertFalse(state['normalWorkerResult'])
            self.assertFalse(state['State']['Running'])
            self.assertEqual(len(calls), 3 if running else 1)

    def test_driver_cleanup_never_stops_or_removes_an_unrelated_worker(self):
        from prepare_osm_native_lock_v1 import IMAGE, settle_error, cleanup_owned
        calls = []
        def call(args):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, json.dumps([{'Id': 'a', 'Image': IMAGE, 'Config': {'Labels': {}}, 'State': {'Running': True}}]), '')
        for cleanup in (lambda p: settle_error(call, None, 'name', 'owner', p, None), lambda p: cleanup_owned(call, None, 'name', 'owner', IMAGE, p)):
            with self.assertRaises(PilotError): cleanup(self.directory())
        self.assertTrue(all(c[1] == 'inspect' for c in calls))


if __name__ == '__main__':
    unittest.main()
