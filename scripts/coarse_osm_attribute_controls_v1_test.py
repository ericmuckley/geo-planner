"""Host scope/isolation controls for the still-unfrozen facts-only runner."""
from copy import deepcopy
import unittest

from coarse_timing_input import PilotError
import run_osm_attribute_controls_v1 as controls


class Tests(unittest.TestCase):
    def plan(self):return {'phase':'attribute_facts_controls_v1','image':controls.IMAGE,'output':controls.OUTPUT,'caps':controls.CAPS,'mounts':controls.MOUNTS,'inputs':dict.fromkeys(controls.MOUNTS,'0'*64),'tests':11}

    def test_exact_scope_and_synthetic_input_allowlist(self):
        controls.validate(self.plan())
        self.assertFalse(any(name.endswith('.pbf') for name in controls.MOUNTS))
        self.assertTrue(all(not name.startswith('src/') for name in controls.MOUNTS))
        self.assertEqual(controls.CAPS['memoryBytes'],512*1024**2)

    def test_recipe_scope_drift_is_rejected(self):
        for key,value in [('phase','other'),('image','other'),('output','other'),('tests',12),('caps',{})]:
            plan=self.plan();plan[key]=value
            with self.assertRaises(PilotError):controls.validate(plan)
        for key in ('mounts','inputs'):
            plan=deepcopy(self.plan());plan[key]['data/source.pbf']='unexpected'
            with self.assertRaises(PilotError):controls.validate(plan)

    def observed(self):
        return {'Image':controls.IMAGE,'Mounts':[{'Destination':'/code/module.py','RW':False},{'Destination':'/work','RW':True}],
                'HostConfig':{'NetworkMode':'none','Memory':536870912,'MemorySwap':536870912,'ReadonlyRootfs':True,'NanoCpus':1000000000,'PidsLimit':32,
                'Tmpfs':{'/tmp':'rw,size=32m'},'CapAdd':None,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],
                'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':33554432,'Hard':33554432}]}}

    def test_hard_resource_security_and_input_permissions_are_verified(self):
        controls.isolation(self.observed())
        for key,value in [('NetworkMode','bridge'),('Memory',1073741824),('MemorySwap',1073741824),('ReadonlyRootfs',False),('NanoCpus',2000000000),('PidsLimit',64),('Tmpfs',{}),('CapAdd',['NET_ADMIN']),('CapDrop',[]),('SecurityOpt',[]),('Ulimits',[])]:
            observed=self.observed();observed['HostConfig'][key]=value
            with self.assertRaises(PilotError):controls.isolation(observed)
        observed=self.observed();observed['Mounts'][0]['RW']=True
        with self.assertRaises(PilotError):controls.isolation(observed)

    def test_positive_fixture_fields_are_retained_without_timing_permission(self):
        import json
        from pathlib import Path
        from coarse_osm_attributes_v1 import way_facts
        repo=Path(__file__).resolve().parents[1];path=next(p for p,target in controls.MOUNTS.items() if target=='/inputs/tiny.jsonl')
        rows=[json.loads(line) for line in (repo/path).read_bytes().splitlines()];nodes={r['element']['id']:r for r in rows if r['element']['type']=='node'}
        for row in rows:
            if row['element']['type']=='way':
                facts=way_facts(row,nodes,snapshot=row['publisherStateUtc'])
                self.assertEqual(facts['sourceRecord'],row);self.assertEqual(facts['carPermission'],'unreviewed');self.assertFalse(facts['usableForTiming'])
                self.assertEqual(facts['speed']['kmh'],88.51392);self.assertEqual(facts['accessTags'],{'access':'private'});self.assertFalse(facts['plainNumericWithoutSpeedScopes'])
