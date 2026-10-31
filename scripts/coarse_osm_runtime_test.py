"""Regression for the observed exit-zero GLIBC mismatch and bounded ELF inputs."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from coarse_osm_runtime import check_loader_result, inspect_library


class Tests(unittest.TestCase):
    def test_observed_exit_zero_glibc_mismatch_is_rejected(self):
        path = Path(__file__).resolve().parents[1] / 'docs/evidence/coarse-osm-runtime-v2-2026-10-26/library-closure-inspection.json'
        result = json.loads(path.read_text()); self.assertEqual(result['exitCode'], 0)
        with self.assertRaisesRegex(Exception, 'closure failed'): check_loader_result(result['exitCode'], result['stdout'], result['stderr'])

    def test_valid_closure(self):
        result = check_loader_result(0, 'libc.so.6 => /lib64/libc.so.6\nlibc.so.6 (GLIBC_2.17) => /lib64/libc.so.6', '')
        self.assertTrue(result['runtimeClosurePassed'])

    def test_missing_library_symbol_or_bad_result_rejected(self):
        for code, text in [(0, 'libc.so.6 => not found'), (0, 'undefined symbol: XML_Parse libc.so.6'), (0, 'statically linked'), (0, ''), (1, 'libc.so.6')]:
            with self.subTest(text=text), self.assertRaises(Exception): check_loader_result(code, text, '')

    def test_output_bound(self):
        with self.assertRaisesRegex(Exception, 'byte cap'): check_loader_result(0, 'libc.so.6' + 'x' * 65536, '')

    def test_elf_sha_machine_type_and_size_before_loader(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'libexpat.so.1'; raw = bytearray(64); raw[:6] = b'\x7fELF\x02\x01'; struct.pack_into('<HH', raw, 16, 3, 183)
            path.write_bytes(raw); sha = hashlib.sha256(raw).hexdigest()
            run = Mock(return_value=SimpleNamespace(returncode=0, stdout='libc.so.6 => /lib64/libc.so.6', stderr=''))
            self.assertEqual(inspect_library(path, sha, run=run)['libraryBytes'], 64)
            with self.assertRaisesRegex(Exception, 'SHA binding'): inspect_library(path, '0' * 64, run=run)
            struct.pack_into('<H', raw, 18, 62); path.write_bytes(raw)
            with self.assertRaisesRegex(Exception, 'aarch64'): inspect_library(path, hashlib.sha256(raw).hexdigest(), run=run)
            path.write_bytes(b'short')
            with self.assertRaisesRegex(Exception, 'file/size'): inspect_library(path, sha, run=run)
            self.assertEqual(run.call_count, 1)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary); (path / 'real').write_bytes(b'x' * 64); (path / 'link').symlink_to('real')
            with self.assertRaisesRegex(Exception, 'file/size'): inspect_library(path / 'link', '0' * 64)


if __name__ == '__main__': unittest.main()
