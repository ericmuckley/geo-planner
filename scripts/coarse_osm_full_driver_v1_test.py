"""Full-stage admission, input, output and resource-boundary controls."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

import run_osm_full_extract_v1 as full
from coarse_osm_records import canonical,strict_json
from coarse_timing_input import PilotError


def plan():
    mounts={full.CATALOG:'/inputs/catalog.json',full.PROPOSAL:'/inputs/proposal.json'}
    return dict(stage='run',phase='full_road_extraction_v1',caps=full.RUN_CAPS,output=full.OUTPUTS['run'],imageId=full.IMAGE,
                network='none',site=full.SITE,runtime=full.RUNTIME,artifact={'path':full.ARTIFACT,'sha256':full.ARTIFACT_SHA},
                prototypeQualification={'recipe':full.REPORT+'/qualification-plan-v8.json',
                    'sha256':'2f502d0943e30cc5e0133f87838248113422cb218f53a399ca606b8b2ea9559f','tests':260,'skips':0},
                proposal=full.PROPOSAL,source=deepcopy(full.SOURCE),catalog=full.CATALOG,semantic=full.SEMANTIC,highwayWays=52053199,
                controllerAdmission={'qualified':True,'tests':14,'producers':{'scripts/coarse_osm_full_resources_v1.py':'a'}},
                mounts=mounts,inputs={full.ARTIFACT:full.ARTIFACT_SHA,full.CATALOG:'b',full.PROPOSAL:'c','scripts/coarse_osm_full_resources_v1.py':'a'},
                workerFiles={'/artifacts/helper.so':full.ARTIFACT_SHA,'/inputs/catalog.json':'b','/inputs/proposal.json':'c'})


class Tests(unittest.TestCase):
    def test_frozen_national_plan_and_admitted_controller(self):
        full.validate(plan())
        for change in ('qualified','tests','producers'):
            damaged=plan();damaged['controllerAdmission'][change]={'qualified':False,'tests':11,'producers':{'scripts/coarse_osm_full_resources_v1.py':'changed'}}[change]
            with self.assertRaises(PilotError):full.validate(damaged)

    def test_resource_source_image_and_prototype_changes_are_rejected(self):
        for key,value in [('caps',full.RUN_CAPS|{'lookupBytesPerPass':full.RUN_CAPS['lookupBytesPerPass']+1}),
                          ('source',full.SOURCE|{'sha256':'bad'}),('imageId','other'),('prototypeQualification',{})]:
            damaged=plan();damaged[key]=value
            with self.assertRaises((PilotError,KeyError)):full.validate(damaged)

    def test_source_cannot_hide_in_input_hash_closure(self):
        damaged=plan();damaged['inputs'][full.SOURCE['path']]=full.SOURCE['sha256']
        with self.assertRaises(PilotError):full.validate(damaged)
        damaged=plan();damaged['mounts']['scripts/../.env']='/code/leak';damaged['inputs']['scripts/../.env']='bad'
        with self.assertRaises(PilotError):full.validate(damaged)

    def test_two_pass_visit_limit_and_original_selected_caps_are_preserved(self):
        path=Path('/inputs/proposal.json')
        if not path.exists():path=Path(__file__).resolve().parents[1]/full.PROPOSAL
        base=strict_json(path.read_bytes());before=deepcopy(base)
        for stage,caps in [('run',full.RUN_CAPS),('controls',full.CONTROL_CAPS)]:
            proposal=full.proposal_for(base,stage,caps)
            self.assertEqual(proposal['proposedCaps']['scanObjectVisitsTotal'],2*full.MAX_VISITS)
            for key in ('selectedUniqueTypedElements','selectedWindowElementOccurrences','pythonSelectionStateBytes','retainedNativeObjectBytes','singleNormalizedElementBytes','normalizedExtractBytes'):
                self.assertEqual(proposal['proposedCaps'][key],base['proposedCaps'][key])
            self.assertEqual(len(proposal['windows']),21 if stage=='run' else 2)
        self.assertEqual(base,before)

    def test_output_ledger_counts_empty_windows_and_rejects_duplicate_objects(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'output';element={'type':'node','id':1}
            row={'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':['a']}
            path.write_bytes(canonical(row)+b'\n');windows=[{'id':'a'},{'id':'b'}]
            ledger=full.output_ledger(path,windows)
            self.assertEqual(ledger['uniqueElements'],1);self.assertEqual(ledger['windows'][1]['elements'],0)
            path.write_bytes((canonical(row)+b'\n')*2)
            with self.assertRaises(PilotError):full.output_ledger(path,windows)

    def test_invalid_field_hash_and_window_memberships_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'output';element={'type':'node','id':1}
            row={'element':element,'elementSha256':hashlib.sha256(canonical(element)).hexdigest(),'windowIds':['a']}
            for damage in ({'elementSha256':'bad'},{'windowIds':[]},{'windowIds':['a','a']},{'windowIds':['other']}):
                path.write_bytes(canonical(row|damage)+b'\n')
                with self.assertRaises(PilotError):full.output_ledger(path,[{'id':'a'}])

    def test_source_hash_and_symlink_boundaries(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'source';raw=b'fixture';path.write_bytes(raw)
            spec={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'md5':hashlib.md5(raw).hexdigest()}
            self.assertEqual(full.source_binding(path,spec,lambda:None,1)['bytesRead'],len(raw))
            with self.assertRaises(PilotError):full.source_binding(path,spec|{'sha256':'bad'},lambda:None,1)
            link=path.with_name('link');link.symlink_to(path)
            with self.assertRaises(PilotError):full.source_binding(link,spec,lambda:None,1)

    def test_isolation_rejects_writable_inputs_or_old_file_limit(self):
        host={'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,
              'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'},'CapAdd':[],
              'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'Ulimits':[{'Name':'core','Soft':0,'Hard':0},
                    {'Name':'fsize','Soft':full.FILE_LIMIT,'Hard':full.FILE_LIMIT}]}
        observed={'Image':full.IMAGE,'HostConfig':host,'Mounts':[{'Destination':'/work','RW':True},{'Destination':'/source.pbf','RW':False}]}
        full.isolation(observed)
        damaged=deepcopy(observed);damaged['Mounts'][1]['RW']=True
        with self.assertRaises(PilotError):full.isolation(damaged)
        damaged=deepcopy(observed);damaged['HostConfig']['Ulimits'][1]['Hard']=67108864
        with self.assertRaises(PilotError):full.isolation(damaged)
