"""Execution closure controls, with all V1 native guards inherited unchanged."""
from copy import deepcopy
import hashlib
import os
import sys
import subprocess
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import coarse_osm_country_screen_v1_test as prior
from coarse_osm_country_screen_v2 import NativeScreen, Resources, run_pair, storage_decision, META
from coarse_osm_projector_v1 import framed_records
from coarse_osm_native_smoke import fixture_records, STATE
from coarse_timing_input import PilotError

ARTIFACT = None
ENGINES = []


def configure_native(path, sha):
    global ARTIFACT
    ARTIFACT = (path, sha)


class HostTests(unittest.TestCase):
    def test_storage_margin_boundaries(self):
        def sample(logical):
            return {'globalManifest': {'shards': [{}]*766, 'directory': {'bytes': 12548800}}, 'logicalWholeIndexBytes': logical}
        self.assertTrue(storage_decision(sample(15*1024**3))['passed'])
        self.assertFalse(storage_decision(sample(20*1024**3))['passed'])
        self.assertEqual(META.size, 100)

    def test_resource_writes_are_owned_bounded_and_include_result_close(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root/'tmp').mkdir()
            fake = {'memory.max': str(4*1024**3), 'memory.swap.max': '0'}
            with patch('coarse_osm_country_screen_v2.resource_metrics', return_value=fake):
                resource = Resources(root, tmp=root/'tmp')
                resource.write(root/'result.json', {'done': True})
                data = resource.result()
                self.assertGreater(data['latest']['work']['logicalBytes'], 0)
                with self.assertRaises(PilotError):
                    resource.write(root/'result.json', {})
                with self.assertRaises(PilotError):
                    resource.write(root.parent/'other', {})
                with self.assertRaises(PilotError):
                    resource.check(force=True, projected=768*1024**2)

    def test_v2_driver_refuses_unqualified_or_drifted_screen(self):
        from run_osm_country_screen_v2 import validate_screen, SCREEN_CAPS, SOURCE
        plan = {'phase':'country_screen_execution_v2', 'caps':deepcopy(SCREEN_CAPS), 'source':deepcopy(SOURCE),
                'output':'data/coarse-quality/us-osm-country-screen-v2','network':'none','imagePull':'never'}
        with self.assertRaises((PilotError, KeyError)):
            validate_screen(plan)


    def test_screen_valid_binding_and_explicit_negative_cases(self):
        from run_osm_country_screen_v2 import (validate_screen,verify_admission,SCREEN_CAPS,SOURCE,SCREEN_OUTPUT,
                                               ADMISSION,ARTIFACT_PATH,IMAGE,SITE,RUNTIME,QUAL_RECIPE)
        pin='0'*64
        source='scripts/coarse_osm_country_screen_v2.py'
        plan={'phase':'country_screen_execution_v2','caps':deepcopy(SCREEN_CAPS),'source':deepcopy(SOURCE),
              'output':SCREEN_OUTPUT,'network':'none','imageId':IMAGE,'imagePull':'never','site':SITE,'runtime':RUNTIME,
              'artifact':{'path':ARTIFACT_PATH,'sha256':pin},'admission':ADMISSION,
              'mounts':{source:'/code/coarse_osm_country_screen_v2.py',ADMISSION:'/inputs/admission.json'},
              'inputs':{source:pin,ADMISSION:pin,ARTIFACT_PATH:pin,QUAL_RECIPE:pin},
              'workerFiles':{'/code/coarse_osm_country_screen_v2.py':pin,'/inputs/admission.json':pin,'/artifacts/country-screen.so':pin}}
        validate_screen(plan)
        for mutation in (lambda p:p.update(network='bridge'),lambda p:p['source'].update(bytes=1),
                         lambda p:p['caps'].update(passSeconds=3001),lambda p:p.update(site='other'),
                         lambda p:p['inputs'].update({SOURCE['path']:pin})):
            bad=deepcopy(plan);mutation(bad)
            with self.assertRaises(PilotError):validate_screen(bad)
        admission={'qualified':True,'linuxSkips':0,'tests':134,'abi':'0x00020000','artifactSha256':pin,
                   'producerFiles':{},'qualificationRecipeSha256':pin,'ownedWorkersAbsent':True,'independentProofPassed':True}
        with self.assertRaises(PilotError):verify_admission(plan,admission)


class NativeTests(prior.NativeTests):
    def engine(self, **kwargs):
        if ARTIFACT is None:
            self.skipTest('Compiled V2 target required')
        engine = NativeScreen(*ARTIFACT, **kwargs)
        ENGINES.append(engine)
        return engine

    def test_type_summaries_are_exact_and_mode_independent(self):
        rows = fixture_records()
        rows[0] = dict(rows[0], timestamp='1970-01-01T00:00:00Z', tags={'é':'😀'}, version=3)
        rows[3] = dict(rows[3], timestamp=STATE, tags={'x':'a'*100})
        engine = self.engine()
        summary = engine.validate_frames(framed_records(rows), STATE, self.caps)
        proof = engine.validate_frames(framed_records(rows), STATE, self.caps, proof=True)
        self.assertEqual(summary['metadata'], proof['metadata'])
        nodes = summary['metadata']['node']
        self.assertEqual(nodes['minTimestamp'], '1970-01-01T00:00:00Z')
        self.assertEqual(nodes['maxTimestamp'], STATE)
        self.assertEqual(nodes['maxTagUtf8Bytes'], 101)
        self.assertEqual(nodes['maxVersion'], 3)
        self.assertEqual(nodes['count'], 4)
        self.assertEqual(summary['metadata']['way']['count'], 3)
        self.assertEqual(summary['metadata']['relation']['maxMembers'], 3)

    def test_aggregate_codec_and_reference_caps_refuse_before_next_call(self):
        engine = self.engine(aggregate_caps={'sourceCodecCalls':2})
        node = framed_records(fixture_records()[:1])
        engine.validate_frames(node, STATE, self.caps)
        with patch.object(engine, 'frames', side_effect=AssertionError('must not call')) as call:
            with self.assertRaisesRegex(PilotError, 'before native call'):
                engine.validate_frames(node, STATE, self.caps)
            call.assert_not_called()
        engine = self.engine(aggregate_caps={'references':2})
        engine.validate_frames(framed_records(fixture_records()[4:5]), STATE, self.caps)
        with self.assertRaisesRegex(PilotError, 'before native call'):
            engine.validate_frames(node, STATE, self.caps)
        self.assertEqual(engine.totals['references'], 2)

    def test_v2_complete_pair_closes_data_and_records(self):
        engine = self.engine()
        rows = fixture_records()
        path = self.pbf(rows)
        root = self.directory()/'pair'
        result = run_pair(path, {'node':4,'way':3,'relation':2}, self.caps, STATE, root, engine, prior.binding(path), minimum_ways=0)
        self.assertEqual(result['objectReceipts'], 18)
        self.assertTrue(result['storageDecision']['passed'])
        closed = json.loads((root/'close-receipt.json').read_text())
        self.assertGreater(closed['secondsThroughResultClose'], result['secondsBeforeResultClose'])
        for stage in result['passes']:
            self.assertGreater(stage['protectedSecondsIncludingReceiptClose'], 0)
        self.assertTrue((root/'pass-a/phase-receipt.json').exists())
        self.assertTrue((root/'pass-b/phase-receipt.json').exists())

    def test_incompatible_v1_consumer_cannot_accept_v2(self):
        from coarse_osm_country_screen_v1 import NativeScreen as Old
        self.engine()
        with self.assertRaises(PilotError):
            Old(*ARTIFACT)

    def test_hard_watchdog_kills_native_framing_and_posthash_stalls(self):
        self.engine()
        path = self.pbf()
        program = """import ctypes,sys,time
import coarse_osm_country_screen_v2 as module
from coarse_osm_country_screen_v2 import NativeScreen
from coarse_osm_native_smoke import STATE
from coarse_timing_input import start_watchdog
engine=NativeScreen(sys.argv[1],sys.argv[2])
phase=sys.argv[4]
caps={'singleNormalizedElementBytes':1048576,'scanNodesPerPass':100,'scanWaysPerPass':100,'scanRelationsPerPass':100,'scanObjectVisitsTotal':100,'pbfHeaderBytesExclusiveMaximum':65536,'pbfUncompressedBlobBytesExclusiveMaximum':33554432}
if phase=='framing':module.framing=lambda *a,**k:time.sleep(10)
def check():
 if phase=='posthash' and not engine.active and engine.last is not None:time.sleep(10)
start_watchdog(.2)
if phase=='no-callback':ctypes.CDLL(None).pause()
else:engine.scan(sys.argv[3],STATE,caps,proof=True,on_record=lambda row:time.sleep(10) if phase=='native-callback' else None,check=check)
"""
        for phase in ('native-callback', 'no-callback', 'framing', 'posthash'):
            result = subprocess.run([sys.executable, '-B', '-c', program, *ARTIFACT, str(path), phase],
                                    capture_output=True, timeout=5, env=os.environ | {'PYTHONPATH': os.pathsep.join(sys.path)})
            self.assertEqual(result.returncode, -9, (phase, result.stderr))


if __name__ == '__main__':
    unittest.main()
