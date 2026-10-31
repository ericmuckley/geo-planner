"""Offline correction controls; never follow package links or execute scripts."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coarse_osm_runtime_package import ZSTD_PATH
from coarse_osm_runtime_package_test import archive, ar
from coarse_osm_runtime_package_v3 import extract_runtime
from setup_osm_tools_v3 import driver, validate_plan


REPO = Path(__file__).resolve().parents[1]
SCOPE = REPO / 'docs/evidence/coarse-osm-tools-v2-run-2026-10-26/offline-correction-scope.json'


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.scope = json.loads(SCOPE.read_text()); self.pin = self.scope['package']

    def fixture(self, extra=None):
        control = b'Package: libexpat1\nVersion: 2.4.7-1ubuntu0.9\nArchitecture: arm64\nDepends: libc6 (>= 2.25)\n'
        entries = [('lib/aarch64-linux-gnu/libexpat.so.1', 'libexpat.so.1.8.7', 'symlink'), ('lib/aarch64-linux-gnu/libexpat.so.1.8.7', b'x' * 64, 'file'),
            ('usr/share/doc/libexpat1/copyright', b'synthetic license', 'file')]
        entries += extra or []
        raw = ar([('debian-binary', b'2.0\n'), ('control.tar.gz', gzip.compress(archive([('control', control, 'file')]))), ('data.tar.gz', gzip.compress(archive(entries)))])
        path = self.root / 'fixture.deb'; path.write_bytes(raw)
        return path, self.pin | {'exactBytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_unselected_valid_library_link_is_validated_but_never_created(self):
        path, pin = self.fixture([('other/alternative.so', 'real.so', 'symlink'), ('other/real.so', b'unselected', 'file')])
        root = self.root / 'runtime'; receipt = extract_runtime(path, pin, root)
        self.assertEqual({p.name for p in root.iterdir()}, {'libexpat.so.1', 'copyright'})
        self.assertTrue(all(p.is_file() and not p.is_symlink() for p in root.iterdir()))
        self.assertEqual(receipt['members']['data']['other/alternative.so']['link'], 'real.so')

    def test_unselected_escape_absolute_dangling_cycle_and_link_chain_rejected(self):
        cases = [[('other/link', '../escape', 'symlink')], [('other/link', '/etc/passwd', 'symlink')], [('other/link', 'absent', 'symlink')],
            [('other/a', 'b', 'symlink'), ('other/b', 'a', 'symlink')], [('other/a', 'b', 'symlink'), ('other/b', 'c', 'symlink'), ('other/c', b'x', 'file')]]
        for extra in cases:
            with self.subTest(extra=extra):
                path, pin = self.fixture(extra)
                with self.assertRaises(Exception): extract_runtime(path, pin, self.root / 'runtime')
                self.assertFalse((self.root / 'runtime').exists())

    def test_duplicate_and_hardlink_remain_rejected(self):
        for extra in [[('lib/aarch64-linux-gnu/libexpat.so.1.8.7', b'other', 'file')], [('other/hard', 'target', 'hardlink')]]:
            path, pin = self.fixture(extra)
            with self.assertRaises(Exception): extract_runtime(path, pin, self.root / 'runtime')

    def test_no_network_recipe_and_hash_refusal(self):
        plan = {'phase': 'cached_runtime_correction_v3', 'output': self.scope['freshOutput'], 'package': self.pin, 'caps': self.scope['caps'],
            'imageId': self.scope['imageId'], 'networks': ['none', 'none'], 'imagePull': 'never',
            'zstd': {'path': ZSTD_PATH, 'sha256': '512958c830b5d563df9e9f245133f1bae1a614fc988c2cbd5bf80db5e0f2cfce', 'versionNumber': 10505},
            'wheels': [{'bytes': 2387931}] + [{'bytes': 1}] * 5, 'reservedReadOnlyInputsBytes': 8388608}
        validate_plan(plan, self.scope); altered = deepcopy(plan); altered['networks'][0] = 'bridge'
        with self.assertRaises(Exception): validate_plan(altered, self.scope)
        with patch('setup_osm_tools_v3.subprocess.run') as run:
            with self.assertRaises(Exception): driver(SCOPE, '0' * 64, self.scope['freshOutput'])
            run.assert_not_called()

    @unittest.skipUnless(Path(ZSTD_PATH).exists(), 'Pinned Linux decoder required for real package fixture')
    def test_actual_saved_package_format_extracts_only_selected_regular_files(self):
        root = self.root / 'runtime'; result = extract_runtime(REPO / self.scope['cachedPackage'], self.pin, root)
        self.assertEqual(result['library']['bytes'], 174168); self.assertEqual(result['copyright']['bytes'], 1756)
        self.assertEqual({p.name for p in root.iterdir()}, {'libexpat.so.1', 'copyright'})
        self.assertFalse(result['packageScriptsExecuted'])


if __name__ == '__main__': unittest.main()
