"""Versioned metadata correction tests; captured seeds and fake HTTP only."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from coarse_osm_bulk_transport import Meter, packaging_api
from coarse_osm_records import canonical
from coarse_timing_input import PilotError
from prepare_osm_lock_v3 import DEPENDENCIES, resolve, validate_plan


REPO = Path(__file__).resolve().parents[1]
PROPOSAL = REPO / 'docs/evidence/coarse-osm-offline-plan-2026-10-26'
SAVED = REPO / 'docs/evidence/coarse-osm-tool-lock-run-2026-10-26/http/001.bin'


class Response:
    def __init__(self, data, status=200):
        self.status = status; self.headers = [('Content-Length', str(len(data)))]; self.data = io.BytesIO(data); self.closed = False
    def read1(self, size): return self.data.read(size)
    def close(self): self.closed = True


class Transport:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def open(self, *args): self.calls.append(args); return self.responses.pop(0)


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name)
        self.proposal = json.loads((PROPOSAL / 'proposal.json').read_text())
        self.osmium = json.loads((PROPOSAL / 'linux-metadata/pyosmium-json.bin').read_bytes())
        self.requests = json.loads(SAVED.read_bytes())
        self.plan = {'phase': 'metadata_only_dependency_lock_v3', 'network': 'bridge', 'caps': {'attempts': 4, 'totalBytes': 16777216, 'kindBytes': {'metadata': 16777216, 'wheel': 0, 'pbf': 0}, 'wallSeconds': 300, 'idleSeconds': 20, 'workingBytes': 536870912, 'errorBytes': 65536},
            'specs': [{'url': f'https://pypi.org/pypi/{n}/json', 'kind': 'metadata', 'maxBytes': 3145728, 'seconds': 20} for n in DEPENDENCIES],
            'memoryBytes': 1073741824, 'tmpBytes': 67108864, 'imagePull': 'never', 'output': 'data/coarse-quality/us-osm-tool-lock-v3'}
        from pip._vendor.packaging.tags import Tag
        self.options = {'tags': [Tag('cp313', 'cp313', 'manylinux_2_28_aarch64'), Tag('py3', 'none', 'any')], 'environment': packaging_api()[-1]()}
        self.options['environment'].update(sys_platform='linux', platform_machine='aarch64', python_version='3.13', python_full_version='3.13.5')
        self.metadata = {}
        for name in DEPENDENCIES:
            version = '2026.10.26' if name == 'certifi' else '2.99' if name == 'urllib3' else '3.99'
            filename = name.replace('-', '_') + '-' + version + '-py3-none-any.whl'
            self.metadata[name] = {'info': {'name': name, 'version': version, 'requires_python': '>=3.10', 'requires_dist': []},
                'urls': [{'filename': filename, 'size': 100, 'url': 'https://files.pythonhosted.org/packages/aa/' + filename, 'digests': {'sha256': 'a' * 64}, 'packagetype': 'bdist_wheel', 'yanked': False}]}

    def execute(self, responses=None, seed=None):
        t = Transport(responses or [Response(canonical(self.metadata[n])) for n in DEPENDENCIES])
        code = resolve(self.root, self.plan, self.proposal, self.osmium, seed or self.requests, transport=t, lock_options=self.options)
        return code, t

    def test_four_urls_and_total_budget_preserved(self):
        validate_plan(self.plan)
        self.assertEqual(len(self.plan['specs']), 4)
        self.assertLess(sum(s['maxBytes'] + 1 for s in self.plan['specs']), self.plan['caps']['totalBytes'])
        self.assertNotIn('requests', DEPENDENCIES)
        for bad in [('phase', 'metadata_only_dependency_lock'), ('output', 'data/coarse-quality/us-osm-tool-lock-v2')]:
            p = deepcopy(self.plan); p[bad[0]] = bad[1]
            with self.assertRaises(PilotError): validate_plan(p)

    def test_closed_lock_reuses_complete_requests_seed(self):
        code, t = self.execute(); self.assertEqual(code, 0); self.assertEqual(len(t.calls), 4)
        lock = json.loads((self.root / 'lock.json').read_text())
        self.assertEqual(len(lock['packages']), 6)
        package = next(p for p in lock['packages'] if p['name'] == 'requests')
        self.assertEqual(package['version'], self.requests['info']['version'])
        self.assertEqual(package['metadataSha256'], hashlib.sha256(canonical(self.requests)).hexdigest())
        self.assertEqual(json.loads((self.root / 'setup-state.json').read_text())['toolBinaryDownloads'], 0)

    def test_catalogue_larger_than_old_cap_below_new_cap_is_kept(self):
        self.metadata['charset-normalizer']['syntheticPadding'] = 'x' * 2390209
        raw = canonical(self.metadata['charset-normalizer']); self.assertGreater(len(raw), 2097152); self.assertLess(len(raw), 3145728)
        code, t = self.execute(); self.assertEqual(code, 0)
        ledger = json.loads((self.root / 'http/http-ledger.json').read_text())
        self.assertEqual(ledger['events'][0]['bodyBytes'], len(raw)); self.assertEqual(len(t.calls), 4)

    def test_oversize_stops_without_read_or_retry(self):
        response = Response(b'x' * 3145729); code, t = self.execute([response])
        self.assertEqual(code, 2); self.assertEqual(len(t.calls), 1)
        self.assertEqual((self.root / 'http/001.bin').stat().st_size, 0)
        state = json.loads((self.root / 'setup-state.json').read_text())
        self.assertEqual(sum(r['status'] == 'unmeasured_after_stop' for r in state['plannedRequests']), 3)
        self.assertFalse((self.root / 'lock.json').exists()); self.assertTrue(response.closed)

    def test_missing_compatible_dependency_never_emits_partial_lock(self):
        self.metadata['idna']['info']['version'] = '5.0'
        code, t = self.execute(); self.assertEqual(code, 2); self.assertEqual(len(t.calls), 4)
        self.assertFalse((self.root / 'lock.json').exists())

    def test_seed_drift_and_attempted_output_refused(self):
        seed = deepcopy(self.requests); seed['info']['version'] = '0.0'
        code, _ = self.execute(seed=seed); self.assertEqual(code, 2)
        with self.assertRaises(FileExistsError): self.execute()


if __name__ == '__main__': unittest.main(verbosity=2)
