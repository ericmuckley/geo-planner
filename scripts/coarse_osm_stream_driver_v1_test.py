"""Driver drift and owned-cleanup controls; no Docker process is launched."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from coarse_timing_input import PilotError
from run_osm_stream_v1 import CAPS, LIMITS, check_isolation, cleanup


class Tests(unittest.TestCase):
    def test_actual_limit_and_readonly_checks(self):
        observed = {'Image': 'image', 'HostConfig': dict(LIMITS, Ulimits=[{'Name': 'core', 'Soft': 0, 'Hard': 0}, {'Name': 'fsize', 'Soft': 67108864, 'Hard': 67108864}]),
            'Mounts': [{'Destination': '/work', 'RW': True}, {'Destination': '/inputs/prefix.pbf', 'RW': False}]}
        check_isolation(observed, 'image')
        for key in LIMITS:
            changed = deepcopy(observed)
            changed['HostConfig'][key] = None
            with self.assertRaises(PilotError):
                check_isolation(changed, 'image')
        observed['Mounts'][1]['RW'] = True
        with self.assertRaises(PilotError):
            check_isolation(observed, 'image')

    def test_no_unrelated_container_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def call(args):
                calls.append(args)
                return subprocess.CompletedProcess(args, 0, json.dumps([{'Config': {'Labels': {}}, 'Image': 'image', 'Id': 'a'}]), '')
            with self.assertRaises(PilotError):
                cleanup(call, None, 'name', 'owner', 'image', Path(temp))
            self.assertEqual(len(calls), 1)

    def test_create_timeout_discovery_and_owned_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def call(args):
                calls.append(args)
                if len(calls) == 1:
                    obj = {'Config': {'Labels': {'geo-planner.stream-owner': 'owner'}}, 'Image': 'image', 'Id': 'a', 'State': {'Running': False}}
                    return subprocess.CompletedProcess(args, 0, json.dumps([obj]), '')
                if len(calls) == 2:
                    return subprocess.CompletedProcess(args, 0, 'a', '')
                return subprocess.CompletedProcess(args, 1, '[]', 'No such object')
            cleanup(call, None, 'name', 'owner', 'image', Path(temp))
            self.assertEqual(calls, [['docker', 'inspect', 'name'], ['docker', 'rm', '-f', 'a'], ['docker', 'inspect', 'a']])
            self.assertTrue(json.loads((Path(temp) / 'cleanup.json').read_text())['independentInspectAbsent'])

    def test_absence_must_be_known_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            def absent(args): return subprocess.CompletedProcess(args, 1, '', 'No such object')
            cleanup(absent, None, 'name', 'owner', 'image', Path(temp))
            self.assertTrue(json.loads((Path(temp) / 'cleanup.json').read_text())['ownedNameAbsent'])
        with tempfile.TemporaryDirectory() as temp:
            def unknown(args): return subprocess.CompletedProcess(args, 1, '', 'Docker unavailable')
            with self.assertRaises(PilotError):
                cleanup(unknown, None, 'name', 'owner', 'image', Path(temp))


if __name__ == '__main__':
    unittest.main()
