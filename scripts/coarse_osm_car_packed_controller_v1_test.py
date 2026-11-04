"""Pre-I/O refusal checks for the bounded country formatter controller."""
import copy
import importlib.util
from pathlib import Path
import unittest

REPO=Path(__file__).resolve().parents[1]
PATH=REPO/'docs/evidence/coarse-osm-car-capacity-2026-11-01/packed_country_driver_v1.py'
if not PATH.exists():PATH=Path(__file__).with_name('packed_country_driver_v1.py')
spec=importlib.util.spec_from_file_location('packed_country_controller',PATH);controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)


def plan():
    return {'stage':'controls','source':controller.SOURCE,'output':controller.OUTPUTS['controls'],
            'image':controller.IMAGE,'caps':copy.deepcopy(controller.CAPS),'priorReserveBytes':64500000000,
            'metadataScratchReserveBytes':104857600,'newClosedAllocations':{'closed':1700000000},
            'mounts':{'scripts/example.py':'/code/example.py'},'hostFiles':{'scripts/example.py':'pin'},'workerFiles':{'/code/example.py':'pin'}}


class PackedControllerTests(unittest.TestCase):
    def test_accepts_exact_finite_configuration(self):controller.validate(plan())

    def test_refuses_cap_and_output_drift(self):
        p=plan();p['caps']['memoryBytes']+=1
        with self.assertRaises(ValueError):controller.validate(p)
        p=plan();p['output']+='-again'
        with self.assertRaises(ValueError):controller.validate(p)

    def test_refuses_source_database_or_parent_path(self):
        for name in ['data/001.bin','data/source.pbf','data/database.sqlite','../outside.py']:
            p=plan();p['mounts']={name:'/repo/input'};p['hostFiles']={name:'pin'};p['workerFiles']={'/repo/input':'pin'}
            with self.assertRaises(ValueError):controller.validate(p)

    def test_refuses_worker_binding_drift(self):
        p=plan();p['workerFiles']['/code/example.py']='wrong'
        with self.assertRaises(ValueError):controller.validate(p)

    def test_refuses_exhausted_retained_budget(self):
        p=plan();p['newClosedAllocations']['closed']=4000000000
        with self.assertRaises(ValueError):controller.validate(p)

    def test_requires_native_controls_and_independent_capture_admission(self):
        p=plan();p['stage']='run';p['output']=controller.OUTPUTS['run'];p['admission']={'nativeLinuxControls':8,'capturedWireBytesIdentical':1027089,'independentCapturedAuditPassed':False}
        with self.assertRaises(ValueError):controller.validate(p)


if __name__=='__main__':unittest.main()
