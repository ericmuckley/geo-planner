"""Synthetic package/transport controls; real cached Zstandard tests run on Linux."""
from copy import deepcopy
import ctypes
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tarfile

from coarse_osm_bulk_test import Response, Transport
from coarse_osm_runtime_package import RuntimeMeter, RuntimeHttps, ZSTD_PATH, ZSTD_SHA, ar_members, decompress, extract_runtime, tar_entries, zstd_api
from setup_osm_tools_v2 import driver, validate_plan
import setup_osm_tools_v2


REPO = Path(__file__).resolve().parents[1]
SCOPE = REPO / 'docs/evidence/coarse-osm-runtime-v2-2026-10-26/next-package-plan.json'


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as stream:
        for name, body, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == 'file': info.size = len(body); stream.addfile(info, io.BytesIO(body))
            else:
                info.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE, 'fifo': tarfile.FIFOTYPE}[kind]; info.linkname = body; stream.addfile(info)
    return output.getvalue()


def ar(members):
    output = bytearray(b'!<arch>\n')
    for name, body in members:
        header = f'{name+"/":<16}{0:<12}{0:<6}{0:<6}{644:<8}{len(body):<10}`\n'.encode(); assert len(header) == 60
        output.extend(header + body + (b'\n' if len(body) % 2 else b''))
    return bytes(output)


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.scope = json.loads(SCOPE.read_text()); self.pin = deepcopy(self.scope['package'])

    def fixture(self, *, prefix='lib', changes=None, control=None):
        control = control or b'Package: libexpat1\nVersion: 2.4.7-1ubuntu0.9\nArchitecture: arm64\nDepends: libc6 (>= 2.25)\n'
        library = bytearray(64); library[:6] = b'\x7fELF\x02\x01'; struct.pack_into('<HH', library, 16, 3, 183)
        entries = [(f'./{prefix}/aarch64-linux-gnu/libexpat.so.1', 'libexpat.so.1.8.7', 'symlink'),
            (f'./{prefix}/aarch64-linux-gnu/libexpat.so.1.8.7', bytes(library), 'file'), ('./usr/share/doc/libexpat1/copyright', b'synthetic license', 'file')]
        if changes: changes(entries)
        raw = ar([('debian-binary', b'2.0\n'), ('control.tar.gz', gzip.compress(archive([('./control', control, 'file'), ('./postinst', b'exit 99', 'file')]))),
            ('data.tar.gz', gzip.compress(archive(entries)))])
        pin = self.pin | {'exactBytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        path = self.root / 'fixture.deb'; path.write_bytes(raw); return path, pin

    def test_exact_pin_and_recipe_guards(self):
        scope = self.scope; plan = {'phase': 'exact_runtime_correction_v2', 'output': scope['freshOutput'], 'package': deepcopy(scope['package']),
            'caps': deepcopy(scope['caps']), 'imageId': scope['imageId'], 'networks': ['bridge', 'none'], 'imagePull': 'never',
            'zstd': {'path': ZSTD_PATH, 'sha256': ZSTD_SHA, 'versionNumber': 10505}, 'wheels': [{'bytes': 2387931}] + [{'bytes': 1}] * 5, 'reservedReadOnlyInputsBytes': 8388608}
        validate_plan(plan, scope)
        for key, value in [('networks', ['bridge', 'bridge']), ('output', '/tmp/unsafe'), ('reservedReadOnlyInputsBytes', -1)]:
            changed = deepcopy(plan); changed[key] = value
            with self.subTest(key=key), self.assertRaises(Exception): validate_plan(changed, scope)

    def test_transfer_refusal_preserves_body_no_retry(self):
        transport = Transport([Response(b'failed', status=502)])
        meter = RuntimeMeter(self.root, self.pin, transport=transport)
        with self.assertRaises(Exception): meter.fetch(0)
        self.assertEqual((self.root / '001.bin').read_bytes(), b'failed'); self.assertEqual(meter.by_kind['runtime'], 6)
        with self.assertRaises(Exception): meter.fetch(0)
        self.assertEqual(len(transport.calls), 1)

    def test_wrong_hash_preserves_exact_length(self):
        meter = RuntimeMeter(self.root, self.pin, transport=Transport([Response(b'x' * 83528)]))
        with self.assertRaisesRegex(Exception, 'SHA256'): meter.fetch(0)
        self.assertEqual(meter.body_bytes, 83528); self.assertEqual(meter.by_kind['wheel'], 0)

    def test_unknown_endpoint_or_pin_before_network(self):
        with self.assertRaises(Exception): RuntimeMeter(self.root, self.pin | {'url': self.pin['url'] + '?mirror=1'})
        with patch('coarse_osm_runtime_package.http.client.HTTPSConnection') as connect:
            with self.assertRaises(Exception): RuntimeHttps().open('https://pypi.org/', 1, 1)
            connect.assert_not_called()

    def test_extract_only_regular_library_and_license_no_scripts(self):
        for prefix in ('lib', 'usr/lib'):
            path, pin = self.fixture(prefix=prefix); root = self.root / prefix.replace('/', '-')
            result = extract_runtime(path, pin, root)
            self.assertEqual({p.name for p in root.iterdir()}, {'libexpat.so.1', 'copyright'})
            self.assertFalse((root / 'libexpat.so.1').is_symlink()); self.assertFalse(result['packageScriptsExecuted'])
            self.assertIn('postinst', result['members']['control'])

    def test_archive_identity_and_reuse_rejected(self):
        path, pin = self.fixture(); root = self.root / 'result'
        with self.assertRaises(Exception): extract_runtime(path, pin | {'sha256': '0' * 64}, root)
        extract_runtime(path, pin, root)
        with self.assertRaises(Exception): extract_runtime(path, pin, root)

    def test_bad_control_identity(self):
        path, pin = self.fixture(control=b'Package: wrong\nVersion: 2.4.7-1ubuntu0.9\nArchitecture: arm64\nDepends: libc6 (>= 2.25)\n')
        with self.assertRaisesRegex(Exception, 'identity/dependency'): extract_runtime(path, pin, self.root / 'result')

    def test_data_symlink_cannot_escape_or_substitute(self):
        for value in ('../escape', '/tmp/escape', 'libc.so.6'):
            path, pin = self.fixture(changes=lambda entries: entries.__setitem__(0, (entries[0][0], value, 'symlink')))
            with self.subTest(value=value), self.assertRaises(Exception): extract_runtime(path, pin, self.root / 'result')

    def test_unexpected_link_or_missing_license(self):
        for change in [lambda e: e.append(('./elsewhere', 'target', 'symlink')), lambda e: e.pop()]:
            path, pin = self.fixture(changes=change)
            with self.assertRaises(Exception): extract_runtime(path, pin, self.root / 'result')

    def test_unsafe_duplicate_and_special_tar_members(self):
        for entries in [[('../escape', b'x', 'file')], [('/escape', b'x', 'file')], [('a', b'x', 'file'), ('./a', b'y', 'file')], [('a', '', 'fifo')], [('a', 'b', 'hardlink')]]:
            with self.subTest(entries=entries), self.assertRaises(Exception): tar_entries(archive(entries))

    def test_file_count_cap(self):
        with self.assertRaisesRegex(Exception, 'file count'): tar_entries(archive([(f'f{i}', b'x', 'file') for i in range(129)]))

    def test_ar_framing_truncation_order_duplicates(self):
        valid = ar([('debian-binary', b'2.0\n'), ('control.tar.gz', b'x'), ('data.tar.gz', b'y')])
        self.assertEqual(len(ar_members(valid)), 2)
        for raw in [valid[:-1], valid + b'x', valid.replace(b'data.tar.gz', b'ctrl.tar.gz'), valid.replace(b'!<arch>', b'?<arch>')]:
            with self.assertRaises(Exception): ar_members(raw)

    def test_compression_bounded_and_framed(self):
        for name, raw in [('control.tar.gz', gzip.compress(b'x' * 1000)), ('data.tar.xz', lzma.compress(b'x' * 1000))]:
            self.assertEqual(decompress(name, raw, 1000), b'x' * 1000)
            for malformed, limit in [(raw, 999), (raw[:-1], 1000), (raw + raw, 2000)]:
                with self.assertRaises(Exception): decompress(name, malformed, limit)
        with self.assertRaises(Exception): decompress('data.tar.other', b'x', 1000)

    def test_recipe_hash_refusal_before_docker(self):
        with patch('setup_osm_tools_v2.subprocess.run') as run:
            with self.assertRaises(Exception): driver(SCOPE, '0' * 64, self.scope['freshOutput'])
            run.assert_not_called()

    def launcher_failure(self, create_timeout=False):
        repo = self.root; (repo / 'scripts').mkdir(); recipe = repo / 'docs/evidence/recipe.json'; recipe.parent.mkdir(parents=True)
        (repo / self.scope['freshOutput']).parent.mkdir(parents=True)
        (repo / 'docs/evidence/scope.json').write_text(json.dumps(self.scope))
        plan = {'phase': 'exact_runtime_correction_v2', 'output': self.scope['freshOutput'], 'package': self.scope['package'],
            'caps': self.scope['caps'], 'imageId': self.scope['imageId'], 'networks': ['bridge', 'none'], 'imagePull': 'never',
            'zstd': {'path': ZSTD_PATH, 'sha256': ZSTD_SHA, 'versionNumber': 10505}, 'wheels': [{'bytes': 2387931}] + [{'bytes': 1}] * 5,
            'reservedReadOnlyInputsBytes': 8388608, 'inputs': {}, 'mounts': {}, 'scope': 'docs/evidence/scope.json'}
        recipe.write_text(json.dumps(plan)); expected = hashlib.sha256(recipe.read_bytes()).hexdigest(); identity = 'a' * 64; calls = []
        limits = {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True,
            'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
        inspected = {'HostConfig': limits, 'Image': plan['imageId'], 'State': {'ExitCode': 2, 'OOMKilled': False}, 'Mounts': []}
        def run(command, **options):
            calls.append(command)
            if command[1] == 'create':
                inspected['Config'] = {'Labels': {'geo-planner.runtime-owner': command[command.index('--label') + 1].split('=', 1)[1]}}
                inspected['Id'] = identity
                if create_timeout: raise subprocess.TimeoutExpired(command, 30)
                return SimpleNamespace(stdout=identity, returncode=0)
            if command[1] == 'rm': return SimpleNamespace(stdout='', returncode=0)
            if any(c[1] == 'rm' for c in calls): return SimpleNamespace(stdout='', stderr='No such object', returncode=1)
            return SimpleNamespace(stdout=json.dumps([inspected]), returncode=0)
        child = SimpleNamespace(poll=lambda: 2, wait=lambda **kw: 2, returncode=2)
        with patch.object(setup_osm_tools_v2, '__file__', str(repo / 'scripts/setup_osm_tools_v2.py')), \
                patch.object(setup_osm_tools_v2.subprocess, 'run', run), patch.object(setup_osm_tools_v2.subprocess, 'Popen', return_value=child):
            if create_timeout:
                with self.assertRaises(subprocess.TimeoutExpired): driver(recipe, expected, self.scope['freshOutput'])
            else: self.assertEqual(driver(recipe, expected, self.scope['freshOutput']), 2)
        output = repo / self.scope['freshOutput']
        self.assertTrue(json.loads((output / 'acquire/cleanup.json').read_text())['independentInspectAbsent'])
        self.assertFalse((output / 'offline').exists()); self.assertEqual(sum(c[1] == 'create' for c in calls), 1)

    def test_failed_owned_worker_cleanup_skips_offline(self): self.launcher_failure()

    def test_create_timeout_discovers_only_labelled_owned_container_and_cleans(self): self.launcher_failure(create_timeout=True)

    @unittest.skipUnless(Path(ZSTD_PATH).exists(), 'Pinned cached Linux decoder only')
    def test_actual_cached_zstd_valid_overflow_truncation_and_concat(self):
        api = zstd_api(); api.ZSTD_compress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]; api.ZSTD_compress.restype = ctypes.c_size_t
        output = ctypes.create_string_buffer(4096); data = b'x' * 1000; count = api.ZSTD_compress(output, len(output), data, len(data), 1)
        self.assertFalse(api.ZSTD_isError(count)); compressed = output.raw[:count]
        self.assertEqual(decompress('data.tar.zst', compressed, 1000), data)
        for raw, limit in [(compressed, 999), (compressed[:-1], 1000), (compressed + compressed, 2000)]:
            with self.assertRaises(Exception): decompress('data.tar.zst', raw, limit)


if __name__ == '__main__': unittest.main()
