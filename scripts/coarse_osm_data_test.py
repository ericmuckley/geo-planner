"""Small data-phase control tests; no live source/provider acquisition."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coarse_osm_bulk_test import Response, Transport
from coarse_osm_data import download_source, extract_source, memory_guard, resource_arithmetic, tree_bytes, validate_plan, verify_completed_data
from prepare_osm_input_v2 import preflight, run_data, validate_capacity, worker


REPO = Path(__file__).resolve().parents[1]
PROPOSAL = REPO / 'docs/evidence/coarse-osm-offline-plan-2026-10-26/proposal.json'
FIXTURE = REPO / 'docs/evidence/coarse-osm-tools-v2-run-2026-10-26/v3/offline/native/fixture.osm.pbf'


def sample_plan():
    p = json.loads(PROPOSAL.read_text()); caps = deepcopy(p['proposedCaps'])
    caps.update(httpAttempts=1, wheelGets=0, metadataGets=0, toolArchiveBodyBytesWithinTotal=0, metadataBodyBytesWithinTotal=0)
    return p, {'phase': 'national_input_v2', 'proposal': str(PROPOSAL.relative_to(REPO)), 'output': p['futureOutput'],
        'extractConfig': {'source': deepcopy(p['source']), 'windows': deepcopy(p['windows']), 'proposedCaps': caps,
            'resourceArithmetic': {'storageComponents': deepcopy(p['resourceArithmetic']['storageComponents'])}},
        'imageId': p['tools']['cachedImageId'], 'imagePull': 'never', 'networks': ['bridge', 'none'], 'reservedReadOnlyInputsBytes': 16777216,
        'activation': {'largerDataLimits': True, 'publisherState': p['source']['proposedPublisherReplicationStateUtc'], 'onlyWhenExactHostCommandExecutes': True},
        'sourceSpec': {'url': p['source']['url'], 'kind': 'pbf', 'maxBytes': p['source']['listedBodyBytes'], 'exactBytes': p['source']['listedBodyBytes'], 'md5': p['source']['publisherMd5'], 'seconds': 5400}}


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); self.root = Path(temp.name).resolve()
        self.proposal, self.plan = sample_plan()

    def tiny_download(self, response=None):
        raw = FIXTURE.read_bytes(); plan = deepcopy(self.plan)
        plan['sourceSpec'].update(maxBytes=len(raw), exactBytes=len(raw), md5=hashlib.md5(raw).hexdigest(), seconds=2)
        plan['extractConfig']['proposedCaps'].update(totalHttpBodyBytes=1048576, workingBytesIncludingTmp=67108864, tmpBytes=65536)
        return plan, Transport([response or Response(raw)])

    def test_exact_source_windows_activation_and_caps(self):
        validate_plan(self.plan, self.proposal)
        for field, value in [('phase', 'wrong'), ('networks', ['bridge', 'bridge']), ('activation', {}), ('output', '/tmp/unsafe')]:
            p = deepcopy(self.plan); p[field] = value
            with self.subTest(field=field), self.assertRaises(Exception): validate_plan(p, self.proposal)
        for mutate in [lambda p: p['extractConfig']['windows'][0]['bbox'].__setitem__(0, 0), lambda p: p['sourceSpec'].__setitem__('url', 'https://download.geofabrik.de/north-america/us-latest.osm.pbf'),
                lambda p: p['extractConfig']['proposedCaps'].__setitem__('httpAttempts', 2)]:
            p = deepcopy(self.plan); mutate(p)
            with self.assertRaises(Exception): validate_plan(p, self.proposal)

    def test_complete_body_and_receipt_without_native_analysis(self):
        plan, transport = self.tiny_download(); receipt = download_source(self.root, plan, 3, transport=transport)
        self.assertEqual(receipt['sha256'], hashlib.sha256(FIXTURE.read_bytes()).hexdigest()); self.assertEqual(len(transport.calls), 1)
        self.assertFalse(receipt['sourceFeasibilityQualified']); self.assertFalse((self.root / 'extract').exists())

    def test_refusal_partial_and_checksum_failures_preserved(self):
        for i, response in enumerate([Response(b'refused', status=502), Response(FIXTURE.read_bytes()[:-1], length=False), Response(b'x' * 564)]):
            root = self.root / str(i); root.mkdir(); plan, transport = self.tiny_download(response)
            with self.assertRaises(Exception): download_source(root, plan, 3, transport=transport)
            self.assertEqual(len(transport.calls), 1); self.assertTrue((root / 'http/http-ledger.json').exists()); self.assertTrue((root / 'http/001.bin').exists())
            self.assertFalse((root / 'source-receipt.json').exists())

    def test_download_reuse_refused_before_second_request(self):
        plan, transport = self.tiny_download(); download_source(self.root, plan, 3, transport=transport)
        with self.assertRaises(Exception): download_source(self.root, plan, 3, transport=transport)
        self.assertEqual(len(transport.calls), 1)

    def test_capacity_and_arithmetic_fail_before_use(self):
        c = self.plan['extractConfig']['proposedCaps']; observed = {'hostDiskAvailableBytes': c['requiredInitialFreeBytes'], 'hostMemoryBytes': 8589934592,
            'dockerMemoryBytes': 6442450944, 'hostCpuCount': 2, 'dockerCpuCount': 2}
        validate_capacity(observed, self.plan['extractConfig'])
        for key in observed:
            changed = dict(observed); changed[key] = 0
            with self.subTest(key=key), self.assertRaises(Exception): validate_capacity(changed, self.plan['extractConfig'])
        result = resource_arithmetic(self.plan['extractConfig'], 16777216); self.assertEqual(result['assignedWorkingBytes'], 65270488400)
        changed = deepcopy(self.plan['extractConfig']); changed['proposedCaps']['sqliteMaxPagesEach'] += 1
        with self.assertRaises(Exception): resource_arithmetic(changed, 16777216)

    def test_new_4g_guard_rejects_wrong_cap_swap_and_unbounded(self):
        path = self.root; (path / 'memory.swap.max').write_text('0')
        with patch('coarse_osm_data.sys.platform', 'linux'):
            (path / 'memory.max').write_text('4294967296'); self.assertEqual(memory_guard(path)['memoryMaxBytes'], 4294967296)
            for value in ('1073741824', 'max', '8589934592'):
                (path / 'memory.max').write_text(value)
                with self.assertRaises(Exception): memory_guard(path)
            (path / 'memory.max').write_text('4294967296'); (path / 'memory.swap.max').write_text('1')
            with self.assertRaises(Exception): memory_guard(path)

    def test_storage_counts_sizes_without_hashing_source_and_rejects_symlink(self):
        (self.root / 'source').write_bytes(b'x' * 1024)
        with patch('hashlib.file_digest', side_effect=AssertionError('Polling must not hash national source')): self.assertEqual(tree_bytes(self.root), 1024)
        (self.root / 'link').symlink_to('source')
        with self.assertRaises(Exception): tree_bytes(self.root)

    def test_unbound_recipe_refused_before_docker_or_output(self):
        with patch('prepare_osm_input_v2.subprocess.run') as run:
            with self.assertRaises(Exception): preflight(PROPOSAL, '0' * 64, self.plan['output'], REPO)
            run.assert_not_called()

    def test_check_mode_does_not_create_output_or_call_docker_start(self):
        with patch('prepare_osm_input_v2.preflight', return_value=(PROPOSAL, self.plan, self.root / 'absent', {})), patch('prepare_osm_input_v2.subprocess.Popen') as start:
            result = run_data(PROPOSAL, '0' * 64, self.plan['output'], repo=REPO, check_only=True)
            self.assertFalse(result['outputCreated']); self.assertFalse((self.root / 'absent').exists()); start.assert_not_called()

    def test_remaining_time_and_identity_are_passed_to_extraction(self):
        state = {'status': 'extracted_publisher_file_analysis_pending', 'sourceIdentity': {'sourceSha256': 'a' * 64, 'sourceMd5': 'b' * 32},
            'passes': [{'status': 'eof'}] * 4, 'independentAuditComplete': True, 'windows': [{'status': 'complete_from_acquired_file_only'}] * 21}
        receipt = {'sha256': 'a' * 64, 'publisherMd5': 'b' * 32}
        with patch('coarse_osm_data.extract_pbf', return_value=state) as extract:
            extract_source(FIXTURE, self.root, self.plan, 12.5, receipt)
            self.assertEqual(extract.call_args.args[1]['proposedCaps']['wallSeconds'], 12.5)
        self.assertFalse(json.loads((self.root / 'analysis-result.json').read_text())['sourceFeasibilityQualified'])

    def test_source_drift_cannot_be_marked_pipeline_success(self):
        state = {'status': 'extracted_publisher_file_analysis_pending', 'sourceIdentity': {'sourceSha256': 'different', 'sourceMd5': 'b' * 32}}
        with patch('coarse_osm_data.extract_pbf', return_value=state), self.assertRaises(Exception): extract_source(FIXTURE, self.root, self.plan, 1, {'sha256': 'a' * 64, 'publisherMd5': 'b' * 32})
        self.assertFalse((self.root / 'analysis-result.json').exists())

    def test_worker_input_drift_stops_before_http_with_all_windows_unqualified(self):
        plan = deepcopy(self.plan); plan['workerFiles'] = {'/code/changed.py': '1' * 64}
        path = self.root / 'recipe.json'; path.write_text(json.dumps(plan)); expected = hashlib.sha256(path.read_bytes()).hexdigest()
        watchdog = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda **kw: 0)
        def binding(p): return expected if Path(p) == path else 'changed'
        # Preserve real recipe/proposal parsing; only input verification and external guards are injected.
        with patch('prepare_osm_input_v2.digest', binding), patch('prepare_osm_input_v2.memory_guard', return_value={'memoryMaxBytes': 4294967296, 'swapMaxBytes': 0}), \
                patch('prepare_osm_input_v2.start_watchdog', return_value=watchdog), patch('prepare_osm_input_v2.download_source') as fetch, \
                patch('prepare_osm_input_v2.verify_worker_inputs', side_effect=ValueError('input drift')):
            # Worker reads the same byte-bound proposal at an internal mount path.
            original_read = Path.read_bytes
            def mounted_read(p): return PROPOSAL.read_bytes() if str(p) == '/inputs/proposal.json' else original_read(p)
            with patch('prepare_osm_input_v2.Path.read_bytes', mounted_read): self.assertEqual(worker(path, expected, self.root, 'download', 10), 2)
            fetch.assert_not_called()
        failure = json.loads((self.root / 'failure.json').read_text()); self.assertEqual(len(failure['windows']), 21)
        self.assertFalse(failure['derivedIndexesTrusted'])

    def launcher_failure(self, *, create_timeout=False, oom=False, deadline=False):
        plan = deepcopy(self.plan); plan.update(mounts={}, runtime={}, site='site')
        (self.root / 'site').mkdir(); output = self.root / 'job'; recipe = self.root / 'recipe.json'; recipe.write_text('{}')
        identity = 'a' * 64; calls = []; clock = [0.]; exit_code = 137 if oom else 2
        hc = {'NetworkMode': 'bridge', 'Memory': 4294967296, 'MemorySwap': 4294967296, 'ReadonlyRootfs': True,
            'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'},
            'Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0}, {'Name': 'fsize', 'Soft': 25769803776, 'Hard': 25769803776}]}
        inspected = {'Image': plan['imageId'], 'Id': identity, 'HostConfig': hc, 'Mounts': [], 'State': {'ExitCode': exit_code, 'OOMKilled': oom}}
        def call(command, **options):
            calls.append(command)
            if command[1] == 'create':
                owner = command[command.index('--label') + 1].split('=', 1)[1]; inspected['Config'] = {'Labels': {'geo-planner.data-owner': owner}}
                if create_timeout: raise subprocess.TimeoutExpired(command, 30)
                return SimpleNamespace(stdout=identity, returncode=0)
            if command[1] == 'rm': return SimpleNamespace(stdout='', returncode=0)
            if any(c[1] == 'rm' for c in calls): return SimpleNamespace(stdout='', stderr='No such object', returncode=1)
            return SimpleNamespace(stdout=json.dumps([inspected]), returncode=0)
        def poll():
            if deadline: clock[0] = 14500.; return None
            return exit_code
        child = SimpleNamespace(poll=poll, wait=lambda **kw: exit_code, kill=lambda: None, returncode=exit_code)
        with patch('prepare_osm_input_v2.preflight', return_value=(recipe, plan, output, {})), patch('prepare_osm_input_v2.subprocess.run', call), \
                patch('prepare_osm_input_v2.subprocess.Popen', return_value=child), patch('prepare_osm_input_v2.time.monotonic', side_effect=lambda: clock[0]):
            if create_timeout or deadline:
                with self.assertRaises(Exception): run_data(recipe, '0' * 64, plan['output'], repo=self.root)
            else: self.assertEqual(run_data(recipe, '0' * 64, plan['output'], repo=self.root), 2)
        self.assertFalse((output / 'extract').exists()); self.assertTrue(json.loads((output / 'download/cleanup.json').read_text())['independentInspectAbsent'])
        if not create_timeout and not deadline:
            stopped = json.loads((output / 'download/driver-stop.json').read_text())
            self.assertEqual(len(stopped['windows']), 21); self.assertEqual(stopped['hardStopCountersMayBePartial'], oom)
        self.assertEqual(sum(c[1] == 'create' for c in calls), 1)

    def test_failed_download_worker_owned_cleanup_all_windows(self): self.launcher_failure()

    def test_oom_marks_partial_counters_untrusted_and_cleans(self): self.launcher_failure(oom=True)

    def test_create_timeout_recovers_only_owned_label(self): self.launcher_failure(create_timeout=True)

    def test_shared_host_deadline_cleans_stalled_owned_worker(self): self.launcher_failure(deadline=True)

    @unittest.skipUnless(Path('/tools/site/osmium').exists(), 'Qualified Linux native fixture only')
    def test_actual_native_wrapper_and_stopped_prefix_with_tiny_source(self):
        sys.path.insert(0, '/tools/site'); plan = deepcopy(self.plan); c = plan['extractConfig']['proposedCaps']
        c.update(sqliteIndexBytesEach=1048576, sqliteMaxPagesEach=256, sqliteCacheBytesEach=8192, workingBytesIncludingTmp=67108864,
            tmpBytes=65536, pythonSelectionStateBytes=4194304, retainedNativeObjectBytes=1048576, normalizedExtractBytes=1048576,
            scanNodesPerPass=100, scanWaysPerPass=100, scanRelationsPerPass=100, scanObjectVisitsTotal=1200)
        plan['extractConfig']['resourceArithmetic']['storageComponents'].update(toolArchivesAndInstalledTree=16777216, metadata=65536)
        plan['extractConfig']['windows'] = [{'id': 'a', 'bbox': [0, 0, 1, 1]}, {'id': 'b', 'bbox': [.25, .25, .75, .75]}]
        raw = FIXTURE.read_bytes(); plan['extractConfig']['source'].update(listedBodyBytes=len(raw), publisherMd5=hashlib.md5(raw).hexdigest())
        receipt = {'sha256': hashlib.sha256(raw).hexdigest(), 'publisherMd5': hashlib.md5(raw).hexdigest()}
        download = self.root / 'download'; download.mkdir(); tiny, transport = self.tiny_download()
        downloaded = download_source(download, tiny, 10, transport=transport)
        plan['sourceSpec'] = tiny['sourceSpec']; output = self.root / 'extract'; output.mkdir()
        state = extract_source(FIXTURE, output, plan, 10, receipt)
        self.assertEqual(state['scanObjectVisits'], 36); self.assertTrue(state['independentAuditComplete'])
        verify_completed_data(self.root, plan)
        stored = download / 'source-receipt.json'; bad = dict(downloaded); bad['sha256'] = '0' * 64; stored.write_text(json.dumps(bad))
        with self.assertRaises(Exception): verify_completed_data(self.root, plan)
        other = self.root / 'stop'; other.mkdir(); c['normalizedExtractBytes'] = 400
        stopped = extract_source(FIXTURE, other, plan, 10, receipt)
        self.assertEqual(stopped['status'], 'stopped'); self.assertFalse(stopped['independentAuditComplete'])
        for row in (other / 'extract/elements.jsonl').read_text().splitlines(): json.loads(row)


if __name__ == '__main__': unittest.main()
