"""Offline config-only redirect, privacy, identity, resource and replay controls."""
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode

import coarse_osm_native_lock_v1 as v1
from coarse_osm_native_lock_v1_test import Reply, Transport, image_replies, source_replies
from coarse_osm_native_lock_v2 import (CAPS, QUERY_KEYS, MANIFEST_PATH, MANIFEST_SHA, MANIFEST_BYTES,
    Metadata, cdn_path, config_url, endpoint, manifest_info, resolve, verify_saved)
from coarse_timing_input import PilotError, json_bytes

SECRET = 'PRIVATE-V2-QUERY-VALUE-MUST-NOT-PERSIST'


def signed(config):
    return 'https://cdn01.quay.io' + cdn_path(config) + '?' + urlencode({k: SECRET for k in QUERY_KEYS})


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root, self.number = Path(temp.name), 0

    def directory(self):
        self.number += 1
        p = self.root / str(self.number); p.mkdir(); return p

    def run_lock(self, *, replies=None, redirect=True, config_change=None, manifest_change=None, **kwargs):
        root = self.directory()
        images = image_replies(config_change=config_change, manifest_change=manifest_change)
        manifest = root / 'manifest.json'; manifest.write_bytes(images[0].body)
        sha = hashlib.sha256(images[0].body).hexdigest()
        config = json.loads(images[0].body)['config']
        if replies is None:
            replies = ([Reply(signed(config).encode(), 302, [('Location', signed(config)), ('Set-Cookie', SECRET)])] if redirect else []) + [images[1]]
            replies += [r for repo, tag in v1.SOURCES for r in source_replies(repo, tag, annotated=True)]
        transport = Transport(replies)
        logs = io.StringIO()
        with redirect_stdout(logs), redirect_stderr(logs):
            code = resolve(root, manifest, manifest_sha=sha, transport=transport, alarm=lambda s: nullcontext(), **kwargs)
        self.assertNotIn(SECRET, logs.getvalue())
        for path in root.rglob('*'):
            if path.is_file(): self.assertNotIn(SECRET.encode(), path.read_bytes(), path.name)
        return code, root, transport, config

    def test_direct_and_one_redirect_locks_and_public_placeholder_replay(self):
        for redirect in (False, True):
            code, root, transport, config = self.run_lock(redirect=redirect)
            self.assertEqual(code, 0, (root / 'result.json').read_text())
            self.assertTrue(verify_saved(root, root / 'manifest.json', manifest_sha=hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest())['completeLockReplayed'])
            self.assertEqual(len(transport.calls), 10 if redirect else 9)
            blobs = [(url, kind) for url, kind, _ in transport.calls if kind != 'git']
            self.assertEqual(blobs, [(config_url(config), 'config')] + ([(signed(config), 'cdn')] if redirect else []))
            self.assertFalse(any('/manifests/' in url or '/auth' in url for url, _, _ in transport.calls))
            self.assertTrue(all(not {'authorization', 'cookie'} & {k.lower() for k in headers} for _, _, headers in transport.calls))
            lock = json.loads((root / 'lock.json').read_text())
            self.assertFalse(lock['fullImportAdmitted'])
            self.assertIsNone(lock['image']['expandedBytes'])
            self.assertTrue(all(s['archiveSha256'] is None for s in lock['sources']))

    def test_wrong_redirect_host_port_path_digest_and_query_shape(self):
        config = json.loads(image_replies()[0].body)['config']
        url = signed(config)
        bad = [url.replace('cdn01.quay.io', 'evil.test'), url.replace('cdn01.quay.io', 'cdn01.quay.io:443'),
            url.replace('cdn01.quay.io', 'user@cdn01.quay.io'), url.replace('https:', 'http:'), url + '#x',
            url.replace(cdn_path(config), '/quayio-production-s3/sha256/aa/' + 'a' * 64),
            url.replace(cdn_path(config), '/other/' + config['digest'][7:]), url + '&extra=value',
            url + '&namespace=value', url.replace('namespace=' + SECRET, 'namespace='),
            url.replace('namespace=' + SECRET, 'namespace=%0Avalue'), url + '\r\nHeader:value',
            url.replace('namespace=' + SECRET, SECRET), url + '&bad=%zz', url + '&bad=%FF',
            url.replace('namespace=' + SECRET, 'namespace=%zz'), url + 'x' * 4096]
        for value in bad:
            with self.subTest(url=value.split('?')[0]):
                code, root, transport, _ = self.run_lock(replies=[Reply(SECRET.encode(), 302, [('Location', value)])])
                self.assertEqual(code, 2)
                self.assertEqual(len(transport.calls), 1)
                self.assertFalse((root / 'lock.json').exists())

    def test_second_hop_auth_errors_and_config_failures_do_not_retry(self):
        config = json.loads(image_replies()[0].body)['config']
        for second in [Reply(SECRET.encode(), 302, [('Location', signed(config))]), Reply(SECRET.encode(), 401),
            Reply(SECRET.encode(), 403), Reply(b'bad', 200), TimeoutError(signed(config))]:
            code, _, transport, _ = self.run_lock(replies=[Reply(SECRET.encode(), 302, [('Location', signed(config))]), second])
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 2)
        for status in (301, 303, 307, 308, 401):
            code, _, transport, _ = self.run_lock(replies=[Reply(SECRET.encode(), status, [('Location', signed(config))])])
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 1)

    def test_platform_rootfs_hash_size_and_saved_manifest_refusals(self):
        mutations = [lambda c: c.update(architecture='amd64'), lambda c: c.update(os='windows'),
            lambda c: c.update(variant='v9'), lambda c: c['rootfs'].update(diff_ids=[]),
            lambda c: c['rootfs'].update(type='unknown'), lambda c: c['rootfs'].update(diff_ids=['sha256:invalid'])]
        for mutate in mutations:
            code, root, transport, _ = self.run_lock(config_change=mutate)
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 2)
            self.assertFalse((root / 'image-lock.json').exists())
        for mutate in [lambda m: m['config'].update(size=m['config']['size'] + 1), lambda m: m['config'].update(digest='sha256:' + 'e' * 64)]:
            self.assertEqual(self.run_lock(manifest_change=mutate)[0], 2)
        transport = Transport([])
        root = self.directory(); manifest = root / 'manifest.json'; manifest.write_bytes(image_replies()[0].body)
        with self.assertRaises(PilotError): resolve(root, manifest, transport=transport)
        self.assertEqual(transport.calls, [])
        for mutate in [lambda m: m.update(schemaVersion=1), lambda m: m.update(layers=[]),
            lambda m: m['layers'][0].update(digest=m['config']['digest']), lambda m: m['layers'][0].update(size=2147483648)]:
            raw = image_replies(manifest_change=mutate)[0].body
            with self.assertRaises(PilotError): manifest_info(raw, hashlib.sha256(raw).hexdigest())

    def test_private_partial_prefixes_headers_and_close_errors_are_redacted(self):
        config = json.loads(image_replies()[0].body)['config']
        class BadClose(Reply):
            def close(self):
                super().close()
                raise ValueError(signed(config))
        replies = [Reply(b'', length=False, partial=SECRET.encode()),
            Reply(SECRET.encode(), headers=[('Content-Encoding', signed(config))]),
            Reply(SECRET.encode(), headers=[('Content-Length', signed(config))]),
            Reply(SECRET.encode(), 302, [('Location', signed(config)), ('Location', signed(config))]),
            BadClose(SECRET.encode(), 403)]
        for reply in replies:
            code, root, transport, _ = self.run_lock(replies=[reply])
            self.assertEqual(code, 2)
            self.assertEqual(len(transport.calls), 1)
            self.assertTrue(reply.closed)
            event = json.loads((root / 'http/ledger.json').read_text())['events'][0]
            self.assertIsNone(event['bodyFile'])
            if reply.partial is None and not reply.body:
                self.assertEqual(event['bodyBytes'], len(SECRET))

    def test_streamed_caps_deadlines_and_bearer_refusal(self):
        config = json.loads(image_replies()[0].body)['config']
        for caps in [dict(CAPS, eachBytes=4), dict(CAPS, totalBytes=4), dict(CAPS, attempts=1)]:
            self.assertEqual(self.run_lock(caps=caps)[0], 2)
        root = self.directory()
        reply = Reply(b'abcdef', length=False)
        meter = Metadata(root / 'http', config, transport=Transport([reply]), caps=dict(CAPS, eachBytes=4), alarm=lambda s: nullcontext())
        with self.assertRaises(PilotError): meter.fetch(config_url(config), 'config')
        self.assertEqual(meter.bytes, 4)
        self.assertTrue(reply.closed)
        clock = [0]
        meter = Metadata(self.directory() / 'http', config, transport=Transport([]), clock=lambda: clock[0])
        with self.assertRaises(PilotError): meter.fetch(config_url(config), 'config', bearer=SECRET)
        self.assertEqual(meter.events, [])
        clock[0] = CAPS['workerSeconds']
        with self.assertRaises(PilotError): meter.fetch(config_url(config), 'config')
        self.assertEqual(meter.events, [])
        with self.assertRaises(PilotError): endpoint(config_url(config).replace(config['digest'], 'sha256:' + 'a' * 64), 'config', config)

    def test_git_stop_preserves_completed_image_and_first_source(self):
        config_reply = image_replies()[1]
        rows = [config_reply] + source_replies(*v1.SOURCES[0]) + [Reply(status=404)]
        code, root, transport, _ = self.run_lock(replies=rows)
        self.assertEqual(code, 2)
        self.assertTrue((root / 'source-1-lock.json').exists())
        self.assertFalse((root / 'lock.json').exists())
        self.assertEqual(len(transport.calls), 5)
        self.assertFalse(verify_saved(root, root / 'manifest.json', manifest_sha=hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest())['completeLockReplayed'])

    def test_v2_plan_pins_manifest_and_only_allows_code_tool_metadata_mounts(self):
        from prepare_osm_native_lock_v2 import IMAGE, validate
        plan = {'phase': 'native_build_metadata_lock_v2', 'caps': deepcopy(CAPS), 'imageId': IMAGE, 'imagePull': 'never',
            'output': 'data/coarse-quality/us-osm-native-lock-v2', 'sources': [list(s) for s in v1.SOURCES],
            'savedManifest': {'path': MANIFEST_PATH, 'sha256': MANIFEST_SHA, 'bytes': MANIFEST_BYTES},
            'phases': {'controls': 'none', 'acquire': 'bridge'}, 'mounts': {MANIFEST_PATH: '/inputs/manifest.json'},
            'inputs': {MANIFEST_PATH: MANIFEST_SHA}, 'workerFiles': {'/inputs/manifest.json': MANIFEST_SHA}}
        validate(plan)
        for mutation in [lambda p: p.update(rootUrl=v1.ROOT_URL), lambda p: p['savedManifest'].update(sha256='f' * 64),
            lambda p: p['savedManifest'].update(path='other'), lambda p: p['caps'].update(attempts=13),
            lambda p: p['mounts'].update({'data/source.pbf': '/inputs/source.pbf'}),
            lambda p: p['workerFiles'].update({'/inputs/manifest.json': 'wrong'})]:
            bad = deepcopy(plan); mutation(bad)
            with self.assertRaises((PilotError, KeyError)): validate(bad)


if __name__ == '__main__': unittest.main()
