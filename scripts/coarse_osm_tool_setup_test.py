"""Tool setup controls with in-memory HTTPS/ZIPs and tiny bounded child processes."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from coarse_osm_bulk_pbf import framing
from coarse_osm_bulk_test import Response, Transport
from coarse_osm_native_smoke import STATE, field, frame, fixture_records, negative_fixtures, write_xml
from setup_osm_tools import SCOPE, SCOPE_SHA, acquire, bounded_process, inventory, validate_plan, wheel_metadata
import setup_osm_tools


REPO = Path(__file__).resolve().parents[1]


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.scope = json.loads((REPO / SCOPE).read_text())
        self.lock = json.loads((REPO / 'docs/evidence/coarse-osm-tool-lock-v3-run-2026-10-26/lock.json').read_text())
        self.plan = {'phase': 'locked_tools_only_v1', 'output': self.scope['newOutput'], 'imageId': self.scope['imageId'], 'scopeSha256': SCOPE_SHA,
            'caps': self.scope['proposedCaps'], 'wheelSpecs': self.scope['wheelSpecs'], 'networks': ['bridge', 'none'], 'imagePull': 'never',
            'inputs': {SCOPE: SCOPE_SHA, **self.scope['inputs']}}

    def synthetic(self):
        archives = []; lock = {'packages': []}; plan = deepcopy(self.plan); plan['wheelSpecs'] = []
        for i in range(6):
            name = 'fixture' + str(i); filename = name + '-1.0-py3-none-any.whl'; raw = io.BytesIO()
            with zipfile.ZipFile(raw, 'w') as zipped:
                zipped.writestr(name + '-1.0.dist-info/METADATA', f'Name: {name}\nVersion: 1.0\nRequires-Python: >=3.10\n')
                zipped.writestr(name + '/__init__.py', '# synthetic\n')
            body = raw.getvalue(); archives.append(body)
            pin = {'name': name, 'version': '1.0', 'filename': filename, 'size': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'dependencies': []}
            lock['packages'].append(pin)
            plan['wheelSpecs'].append({'url': 'https://files.pythonhosted.org/packages/' + filename, 'kind': 'wheel', 'maxBytes': len(body), 'exactBytes': len(body), 'sha256': pin['sha256'], 'seconds': 2})
        return plan, lock, archives

    def test_exact_scope_and_no_drift(self):
        self.assertEqual(hashlib.sha256((REPO / SCOPE).read_bytes()).hexdigest(), SCOPE_SHA)
        validate_plan(self.plan, self.scope, self.lock)
        for key, value in [('networks', ['bridge', 'bridge']), ('imagePull', 'always'), ('output', '/tmp/wrong'), ('caps', {})]:
            plan = deepcopy(self.plan); plan[key] = value
            with self.subTest(key=key), self.assertRaises(Exception): validate_plan(plan, self.scope, self.lock)
        plan = deepcopy(self.plan); plan['wheelSpecs'][0]['url'] += '?mirror=1'
        with self.assertRaises(Exception): validate_plan(plan, self.scope, self.lock)

    def test_six_wheel_acquisition_validation_and_no_retry(self):
        plan, lock, archives = self.synthetic(); transport = Transport([Response(body) for body in archives])
        result = acquire(self.root, plan, lock, transport=transport)
        self.assertEqual(len(transport.calls), 6); self.assertEqual(result['archiveBytes'], sum(map(len, archives)))
        self.assertEqual(len(result['packages']), 6); self.assertTrue((self.root / 'http/http-ledger.json').exists())
        with self.assertRaises(Exception): acquire(self.root, plan, lock, transport=transport)
        self.assertEqual(len(transport.calls), 6)

    def test_hash_failure_retains_body_and_skips_remaining(self):
        plan, lock, archives = self.synthetic(); transport = Transport([Response(archives[0][:-1] + b'x')])
        with self.assertRaises(Exception): acquire(self.root, plan, lock, transport=transport)
        self.assertEqual(len(transport.calls), 1); self.assertTrue((self.root / 'http/001.bin').exists())
        self.assertFalse((self.root / 'acquisition.json').exists())

    def test_aggregate_validation_cap(self):
        plan, lock, archives = self.synthetic(); plan['caps']['unpackedValidationBytes'] = 1
        with self.assertRaises(Exception): acquire(self.root, plan, lock, transport=Transport([Response(body) for body in archives]))
        self.assertEqual(len(list((self.root / 'http').glob('*.bin'))), 6)
        self.assertFalse((self.root / 'acquisition.json').exists())

    def test_actual_dependency_metadata_drift(self):
        folder = self.root / 'test-1.dist-info'; folder.mkdir()
        (folder / 'METADATA').write_text('Name: test\nVersion: 1\nRequires-Dist: requests>=2\n')
        pin = {'name': 'test', 'version': '1', 'filename': 'test-1-py3-none-any.whl', 'dependencies': []}
        with self.assertRaisesRegex(Exception, 'differs from saved lock'): wheel_metadata(self.root, pin, {'packages': []})

    def test_subprocess_success_and_logs(self):
        log = bounded_process([sys.executable, '-B', '-c', 'print("fixture")'], self.root, 2, 10000)
        self.assertEqual(log, b'fixture\n'); self.assertEqual((self.root / 'child.log').read_bytes(), log)

    def test_subprocess_timeout_kills_and_preserves(self):
        with self.assertRaisesRegex(Exception, 'deadline'):
            bounded_process([sys.executable, '-B', '-c', 'import time;time.sleep(3)'], self.root, .05, 10000)
        self.assertTrue((self.root / 'child.log').exists())

    def test_subprocess_failure_log_and_exit(self):
        with self.assertRaisesRegex(Exception, 'Offline child failed'):
            bounded_process([sys.executable, '-B', '-c', 'print("failed");raise SystemExit(2)'], self.root, 2, 10000)
        self.assertIn(b'failed', (self.root / 'child.log').read_bytes())

    def test_subprocess_output_log_cap(self):
        with self.assertRaisesRegex(Exception, 'log cap'):
            bounded_process([sys.executable, '-B', '-c', 'print("x"*1000)'], self.root, 2, 10000, log_limit=10)
        self.assertEqual((self.root / 'child.log').stat().st_size, 10)

    def test_subprocess_tree_cap(self):
        script = 'from pathlib import Path;import time;Path(' + repr(str(self.root / 'oversize')) + ').write_bytes(b"x"*1000);time.sleep(3)'
        with self.assertRaisesRegex(Exception, 'tree byte cap'): bounded_process([sys.executable, '-B', '-c', script], self.root, 2, 10)

    def test_inventory_detects_bytes_files_and_symlink(self):
        (self.root / 'a').write_bytes(b'abc'); self.assertEqual(inventory(self.root, 3)['bytes'], 3)
        with self.assertRaises(Exception): inventory(self.root, 2)
        with self.assertRaises(Exception): inventory(self.root, 3, 0)
        (self.root / 'link').symlink_to('a')
        with self.assertRaisesRegex(Exception, 'symlink'): inventory(self.root, 100)

    def test_xml_fixture_collision_raw_tags_and_external_members(self):
        rows = fixture_records(); write_xml(self.root / 'fixture.osm', rows)
        self.assertEqual(len(rows), 9); self.assertEqual({r['type'] for r in rows if r['id'] == 1}, {'node', 'way', 'relation'})
        self.assertEqual(rows[4]['tags']['access'], 'private'); self.assertEqual(rows[7]['members'][-1]['ref'], 999)
        self.assertIn(b'maxspeed:conditional', (self.root / 'fixture.osm').read_bytes())

    def test_negative_frame_controls(self):
        caps = {'pbfHeaderBytesExclusiveMaximum': 65536, 'pbfUncompressedBlobBytesExclusiveMaximum': 33554432}
        # The valid control uses the same exact state conversion as the framing specification.
        import datetime
        stamp = int(datetime.datetime.fromisoformat(STATE.replace('Z', '+00:00')).timestamp())
        valid = frame(b'OSMHeader', field(4, b'OsmSchema-V0.6') + field(32, stamp)) + frame(b'OSMData', field(1, b''))
        path = self.root / 'control.pbf'; path.write_bytes(valid); self.assertEqual(framing(path, caps, STATE)['frames'], 2)
        for name, (raw, message) in negative_fixtures(valid).items():
            with self.subTest(name=name):
                path.write_bytes(raw)
                with self.assertRaisesRegex(Exception, message): framing(path, caps, STATE)

    def test_driver_refuses_unbound_recipe_before_docker(self):
        with patch('setup_osm_tools.subprocess.run') as run:
            with self.assertRaises(Exception): setup_osm_tools.driver(REPO / SCOPE, '0' * 64, self.scope['newOutput'])
            run.assert_not_called()

    def test_new_launcher_failed_worker_owned_cleanup_and_no_offline_stage(self):
        repo = self.root; (repo / 'scripts').mkdir(); recipe = repo / 'docs/evidence/recipe.json'; recipe.parent.mkdir(parents=True)
        (repo / self.scope['newOutput']).parent.mkdir(parents=True)
        scope_path = repo / SCOPE; scope_path.parent.mkdir(parents=True); scope_path.write_text(json.dumps(self.scope))
        plan = deepcopy(self.plan); plan.update(lock='docs/evidence/lock.json', mounts={})
        recipe.write_text(json.dumps(plan)); (repo / plan['lock']).write_text(json.dumps(self.lock))
        identity = 'a' * 64; calls = []
        hc = {'NetworkMode': 'bridge', 'Memory': 1073741824, 'MemorySwap': 1073741824, 'ReadonlyRootfs': True,
            'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=64m'}}
        inspected = {'HostConfig': hc, 'Image': plan['imageId'], 'State': {'ExitCode': 2, 'OOMKilled': False}, 'Mounts': []}
        def run(command, **options):
            calls.append(command)
            if command[1] == 'create': return SimpleNamespace(stdout=identity, returncode=0)
            if command[1] == 'rm': return SimpleNamespace(stdout='', returncode=0)
            if any(c[1] == 'rm' for c in calls): return SimpleNamespace(stdout='', stderr='No such object', returncode=1)
            return SimpleNamespace(stdout=json.dumps([inspected]), returncode=0)
        def fake_digest(path):
            path = Path(path)
            if path == recipe: return 'b' * 64
            return plan['inputs'].get(str(path.relative_to(repo)), hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)
        child = SimpleNamespace(poll=lambda: 2, wait=lambda **kw: 2, returncode=2)
        with patch.object(setup_osm_tools, '__file__', str(repo / 'scripts/setup_osm_tools.py')), patch.object(setup_osm_tools, 'digest', fake_digest), \
                patch.object(setup_osm_tools.subprocess, 'run', run), patch.object(setup_osm_tools.subprocess, 'Popen', return_value=child):
            self.assertEqual(setup_osm_tools.driver(recipe, 'b' * 64, self.scope['newOutput']), 2)
        output = repo / self.scope['newOutput']
        self.assertTrue(json.loads((output / 'acquire/cleanup.json').read_text())['independentInspectAbsent'])
        self.assertFalse((output / 'offline').exists()); self.assertEqual(sum(c[1] == 'create' for c in calls), 1)


if __name__ == '__main__': unittest.main()
