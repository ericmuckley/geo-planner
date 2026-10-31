"""Controller admission, bounded witness flow and independent coordinate checks."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_osm_way_batch_v2 as batch
from coarse_osm_country_screen_v1 import OwnedStorage
from coarse_timing_input import PilotError


def plan():
    return dict(stage='controls',phase='bounded_way_batch_v2',caps=deepcopy(batch.CONTROL_CAPS),output=batch.OUTPUTS['controls'],
                imageId=batch.IMAGE,network='none',artifact={'path':batch.ARTIFACT,'sha256':batch.ARTIFACT_SHA},site=batch.SITE,runtime=batch.RUNTIME,
                parentSeal=batch.PARENT_SEAL,helperQualificationTests=206,helperQualificationSkips=0,expectedWays=200,expectedSemantic='a'*64,
                source=dict(path=batch.FIXTURE+'/fixture.pbf',bytes=3,sha256=hashlib.sha256(b'abc').hexdigest(),md5=hashlib.md5(b'abc').hexdigest(),
                            publisherState='2026-10-25T21:21:21Z',counts={'node':300,'way':200,'relation':0}),probe=batch.FIXTURE+'/two-pass/pass-b/probe',
                inputs={batch.ARTIFACT:batch.ARTIFACT_SHA},workerFiles={'/artifacts/helper.so':batch.ARTIFACT_SHA},mounts={})


class Reader:
    def __init__(self):self.loaded_bytes=0
    def points(self,keys):
        self.loaded_bytes+=100
        return [[identity/10,identity/20] for identity in keys]


class Tests(unittest.TestCase):
    def test_caps_source_and_network_drift_are_rejected(self):
        valid=plan();batch.validate(valid)
        for mutate in (lambda p:p['caps'].update(lookupBytes=p['caps']['lookupBytes']+1),lambda p:p.update(network='default'),
                       lambda p:p.update(probe='other'),lambda p:p['source']['counts'].update(node=301)):
            bad=deepcopy(valid);mutate(bad)
            with self.assertRaises(PilotError):batch.validate(bad)

    def test_real_measurement_requires_qualified_exact_controller(self):
        valid=plan();valid.update(stage='run',caps=deepcopy(batch.RUN_CAPS),output=batch.OUTPUTS['run'],source=batch.SOURCE,probe=batch.PROBE,expectedWays=274570,
                                 expectedSemantic='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16',
                                 controllerAdmission={'qualified':True,'tests':7,'producers':{'scripts/controller.py':'b'*64}})
        valid['inputs']['scripts/controller.py']='b'*64;batch.validate(valid)
        for mutate in (lambda p:p['controllerAdmission'].update(qualified=False),lambda p:p['inputs'].update({'scripts/controller.py':'c'*64})):
            bad=deepcopy(valid);mutate(bad)
            with self.assertRaises(PilotError):batch.validate(bad)

    def sink(self,folder,reader=None):
        root=Path(folder);return batch.BatchSink(reader or Reader(),root/'witness',OwnedStorage(root),lambda:None,batch.CONTROL_CAPS)

    def test_duplicate_reference_order_and_bits_survive_independent_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            sink=self.sink(folder);sink.receive([{'type':'way','id':9,'nodes':[2,1,2]}])
            raw=(sink.root/'0000.bin').read_bytes()
            self.assertEqual(list(batch.WITNESS.iter_unpack(raw)),[(2,.2,.1),(1,.1,.05),(2,.2,.1)])
            proof=batch.audit_witnesses(sink.root,sink.ledger,Reader(),lambda:None)
            self.assertEqual(proof['references'],3)
            self.assertEqual(proof['orderedWitnessSha256'],hashlib.sha256(raw).hexdigest())

    def test_independent_audit_rejects_coordinate_corruption_even_with_matching_file_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            sink=self.sink(folder);sink.receive([{'type':'way','id':9,'nodes':[1,2]}])
            path=sink.root/'0000.bin';raw=bytearray(path.read_bytes());raw[:batch.WITNESS.size]=batch.WITNESS.pack(1,9.,9.);path.write_bytes(raw)
            sink.ledger[0]['witnessSha256']=hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(PilotError,'ordered coordinate bits'):
                batch.audit_witnesses(sink.root,sink.ledger,Reader(),lambda:None)

    def test_wrong_returned_count_stops_before_witness_write(self):
        reader=Reader();reader.points=lambda keys:[]
        with tempfile.TemporaryDirectory() as folder:
            sink=self.sink(folder,reader)
            with self.assertRaisesRegex(PilotError,'occurrence count'):sink.receive([{'type':'way','id':9,'nodes':[1,2]}])
            self.assertEqual(list(sink.root.iterdir()),[])

    def test_reference_decoder_budget_refuses_before_decode(self):
        codec=batch.AuditCodec(dict(lookupRows=1,codecCalls=1))
        with self.assertRaisesRegex(PilotError,'decode cap'):codec.decode(b'invalid',2,1,2)
        self.assertEqual((codec.rows,codec.calls),(0,0))

    def test_input_paths_do_not_replace_owned_container_name(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=Path(folder).resolve();source=repo/batch.FIXTURE/'fixture.pbf';source.parent.mkdir(parents=True);source.write_bytes(b'abc')
            recipe=repo/'docs/evidence/recipe.json';recipe.parent.mkdir(parents=True);recipe.write_text(json.dumps(plan()));pin='d'*64
            refusal=subprocess.CompletedProcess([],1,'','intentional Docker create refusal')
            with patch.object(batch,'__file__',str(repo/'scripts/controller.py')),patch.object(batch,'sha',side_effect=lambda p:pin if Path(p)==recipe else batch.ARTIFACT_SHA),\
                 patch.object(batch,'capacity',return_value={'dockerMemoryBytes':8*1024**3,'hostMemoryBytes':16*1024**3}),\
                 patch.object(batch.shutil,'disk_usage',return_value=type('Disk',(),{'free':8*1024**3})()),\
                 patch.object(batch.subprocess,'run',return_value=refusal) as run,patch.object(batch,'cleanup_owned'),patch.object(batch,'settle_error'):
                self.assertEqual(batch.driver(recipe,pin),2)
            args=run.call_args_list[0].args[0]
            self.assertRegex(args[args.index('--name')+1],r'^geo-planner-way-batch-[0-9a-f]{12}$')
            self.assertIn('--network=none',args);self.assertIn('--memory=4g',args);self.assertIn('--read-only',args)


if __name__=='__main__':unittest.main()
