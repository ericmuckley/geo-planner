"""Regression for the actual stat/checkpoint race; no source requests."""
from copy import deepcopy
import os
from pathlib import Path
import json
import subprocess
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from coarse_osm_data import tree_bytes as frozen_v2_tree
from coarse_osm_data_v3 import tree_bytes, validate_plan
from coarse_osm_data_test import sample_plan
import prepare_osm_input_v3 as launcher


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup); self.root = Path(temporary.name).resolve()

    def test_frozen_monitor_false_special_error_is_reproducible(self):
        checkpoint = self.root / 'http-ledger.partial'; checkpoint.write_bytes(b'checkpoint')
        original = Path.is_dir
        def renamed(path):
            if path == checkpoint:
                checkpoint.unlink(); return False
            return original(path)
        with patch.object(Path, 'is_dir', renamed), self.assertRaisesRegex(Exception, 'Special data output'): frozen_v2_tree(self.root)

    def test_vanished_checkpoint_is_skipped_before_classification(self):
        checkpoint = self.root / 'http-ledger.partial'; checkpoint.write_bytes(b'checkpoint'); (self.root / 'body.bin').write_bytes(b'body')
        original = Path.lstat
        def renamed(path):
            if path == checkpoint:
                checkpoint.unlink(); raise FileNotFoundError(str(path))
            return original(path)
        with patch.object(Path, 'lstat', renamed): self.assertEqual(tree_bytes(self.root), 4)

    def test_unlinked_after_snapshot_uses_one_consistent_size(self):
        checkpoint = self.root / 'checkpoint'; checkpoint.write_bytes(b'12345'); original = Path.lstat
        def renamed(path):
            value = original(path)
            if path == checkpoint: checkpoint.unlink()
            return value
        with patch.object(Path, 'lstat', renamed): self.assertEqual(tree_bytes(self.root), 5)

    def test_same_path_atomic_replacement_is_sized_from_snapshot(self):
        checkpoint = self.root / 'checkpoint'; checkpoint.write_bytes(b'12345'); original = Path.lstat
        def replaced(path):
            value = original(path)
            if path == checkpoint:
                pending = self.root / 'replacement'; pending.write_bytes(b'x' * 100); pending.replace(checkpoint)
            return value
        with patch.object(Path, 'lstat', replaced): self.assertEqual(tree_bytes(self.root), 5)
        self.assertEqual(tree_bytes(self.root), 100)

    def test_real_special_entries_and_symlinks_still_rejected(self):
        (self.root / 'file').write_bytes(b'abc'); (self.root / 'link').symlink_to('file')
        with self.assertRaises(Exception): tree_bytes(self.root)
        (self.root / 'link').unlink(); os.mkfifo(self.root / 'fifo')
        with self.assertRaises(Exception): tree_bytes(self.root)

    def test_no_payload_hashing_or_multiple_type_queries(self):
        (self.root / 'file').write_bytes(b'abc')
        with patch('hashlib.file_digest', side_effect=AssertionError('No body hashing')), patch.object(Path, 'is_file', side_effect=AssertionError('One lstat only')):
            self.assertEqual(tree_bytes(self.root), 3)

    def test_concurrent_checkpoint_replacements_do_not_false_stop(self):
        stop = threading.Event(); errors = []
        def writer():
            try:
                while not stop.is_set():
                    pending = self.root / 'checkpoint.partial'; pending.write_bytes(b'x' * 1024); pending.replace(self.root / 'checkpoint.json')
            except Exception as error: errors.append(error)
        thread = threading.Thread(target=writer); thread.start()
        try:
            for _ in range(1000): self.assertLessEqual(tree_bytes(self.root), 2048)
        finally: stop.set(); thread.join(timeout=3)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])

    def test_version_changes_only_phase_output_not_source_limits_or_windows(self):
        proposal, plan = sample_plan(); plan.update(phase='national_input_v3', output='data/coarse-quality/us-osm-input-v3')
        validate_plan(plan, proposal)
        for change in [lambda p: p['sourceSpec'].__setitem__('seconds', 5500), lambda p: p['extractConfig']['windows'][0]['bbox'].__setitem__(0, 0),
                lambda p: p['extractConfig']['proposedCaps'].__setitem__('httpAttempts', 2), lambda p: p.__setitem__('output', 'data/coarse-quality/us-osm-input-v2')]:
            modified = deepcopy(plan); change(modified)
            with self.assertRaises(Exception): validate_plan(modified, proposal)

    def launcher_failure(self, *, interrupt=False, create_timeout=False):
        _, plan = sample_plan(); plan.update(phase='national_input_v3', output='data/coarse-quality/us-osm-input-v3', mounts={}, runtime={}, site='site')
        (self.root / 'site').mkdir(); output = self.root / 'job'; recipe = self.root / 'recipe.json'; recipe.write_text('{}')
        identity = 'b' * 64; calls = []; polls = [0]
        hc = {'NetworkMode': 'bridge', 'Memory': 4294967296, 'MemorySwap': 4294967296, 'ReadonlyRootfs': True,
            'NanoCpus': 2000000000, 'PidsLimit': 64, 'Tmpfs': {'/tmp': 'rw,size=256m'},
            'Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0}, {'Name': 'fsize', 'Soft': 25769803776, 'Hard': 25769803776}]}
        inspected = {'Image': plan['imageId'], 'Id': identity, 'HostConfig': hc, 'Mounts': [], 'State': {'ExitCode': 2, 'OOMKilled': False}}
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
            polls[0] += 1
            if interrupt and polls[0] == 1: raise KeyboardInterrupt()
            return 2
        child = SimpleNamespace(poll=poll, wait=lambda **kw: 2, kill=lambda: None, returncode=2)
        with patch.object(launcher, 'preflight', return_value=(recipe, plan, output, {})), patch.object(launcher.subprocess, 'run', call), patch.object(launcher.subprocess, 'Popen', return_value=child):
            if interrupt:
                with self.assertRaises(KeyboardInterrupt): launcher.run_data(recipe, '0' * 64, plan['output'], repo=self.root)
            elif create_timeout:
                with self.assertRaises(subprocess.TimeoutExpired): launcher.run_data(recipe, '0' * 64, plan['output'], repo=self.root)
            else: self.assertEqual(launcher.run_data(recipe, '0' * 64, plan['output'], repo=self.root), 2)
        self.assertTrue((output / 'download/container-before-removal.json').exists())
        self.assertTrue(json.loads((output / 'download/cleanup.json').read_text())['independentInspectAbsent'])
        self.assertFalse((output / 'extract').exists()); self.assertEqual(sum(c[1] == 'create' for c in calls), 1)
        if not create_timeout: self.assertTrue((output / 'download/container-initial.json').exists())
        if interrupt: self.assertEqual(json.loads((output / 'download/driver-failure.json').read_text())['errorType'], 'KeyboardInterrupt')

    def test_failed_worker_keeps_initial_and_pre_removal_snapshot(self): self.launcher_failure()

    def test_keyboard_interrupt_preserves_failure_diagnostics_and_cleans(self): self.launcher_failure(interrupt=True)

    def test_create_timeout_still_recovers_owned_label_and_snapshots(self): self.launcher_failure(create_timeout=True)


if __name__ == '__main__': unittest.main()
