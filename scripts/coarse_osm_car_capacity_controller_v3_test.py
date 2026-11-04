"""Fail missing run inputs before country I/O; no ignored assets or native library."""
from copy import deepcopy
import unittest

import run_osm_car_capacity_v3 as runner
from coarse_timing_input import PilotError


def plan():
    partition=runner.OUTPUTS['derive']+'/splits.u64'
    mounts={partition:'/inputs/splits.u64',runner.PRIOR:'/'+runner.PRIOR,
            'docs/evidence/coarse-osm-national-footprint-2026-11-01/raw-run-v1/receipt.json':'/inputs/footprint-receipt.json'}
    return {'stage':'run','phase':'native_car_capacity_v3','caps':runner.CAPS,'source':runner.SOURCE,'scanCaps':runner.SCAN,
            'image':runner.IMAGE,'flags':runner.FLAGS,'policy':runner.POLICY,'output':runner.OUTPUTS['run'],
            'network':'none','imagePull':'never','mounts':mounts,'inputs':dict.fromkeys(mounts,'synthetic-pin'),'tests':runner.TESTS,
            'rootfs':{'path':runner.ASSET_ROOT},'headers':{key:{'path':value} for key,value in runner.HEADERS.items()},
            'newClosedAllocations':{},'artifact':{'path':runner.OUTPUTS['build']+'/car-capacity.so'},
            'admission':{'tests':68,'successful':True,'skips':0},'partition':{'qualified':True,'path':partition}}


class Tests(unittest.TestCase):
    def test_complete_required_bindings_and_fresh_version(self):
        p=plan();runner.validate(p)
        self.assertEqual(p['output'],'data/coarse-quality/us-osm-car-capacity-run-v3')
        self.assertEqual(p['artifact']['path'],'data/coarse-quality/us-osm-car-capacity-build-v1/car-capacity.so')

    def test_each_missing_binding_fails_even_with_matching_rosters(self):
        for name in plan()['mounts']:
            p=deepcopy(plan());p['mounts'].pop(name);p['inputs'].pop(name)
            with self.assertRaisesRegex(PilotError,'missing required run binding'):
                runner.validate(p)

    def test_wrong_worker_destination_fails_before_input_read(self):
        for name in plan()['mounts']:
            p=deepcopy(plan());p['mounts'][name]='/inputs/wrong-reference.json'
            with self.assertRaisesRegex(PilotError,'missing required run binding'):
                runner.validate(p)

    def test_original_guards_and_envelope_remain_required(self):
        for field,value in [('source',{}),('caps',{}),('policy',{}),('network','bridge'),('tests',67),('inputs',{})]:
            p=plan();p[field]=value
            with self.assertRaises(PilotError):
                runner.validate(p)
