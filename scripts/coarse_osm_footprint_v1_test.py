"""Independent histogram fixtures and inherited whole-source guard controls."""
from copy import deepcopy
import ctypes
import struct
import unittest

import coarse_osm_country_screen_v1_test as prior
from coarse_osm_footprint_v1 import NativeScreen
from coarse_osm_footprint_summary_v1 import TOTALS,ROAD,MAJOR,decode_histogram,profile,reconcile,storage_bounds
from coarse_osm_country_wire_v4 import framed_records,reference_seal
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_timing_input import PilotError

ARTIFACT=None


def fixture():
    rows=fixture_records();common={k:rows[4][k] for k in ('type','version','timestamp','visible')}
    extra=[dict(common,id=10+i,nodes=[1,2,3,1] if i%2 else [1,2],tags={'highway':role}) for i,role in enumerate((*MAJOR,'','imaginary;雪','residential','primary_link;secondary'))]
    extra.append(dict(common,id=99,nodes=[1]*1025,tags={'highway':'primary'}))
    return rows[:7]+extra+rows[7:]


def oracle(rows):
    totals=dict.fromkeys(TOTALS,0);roads={};restrictions={}
    for row in rows:
        kind=row['type'];totals[kind+'s']+=1;totals['tagged'+kind.title()+'s']+=bool(row['tags'])
        if kind=='way':
            n=len(row['nodes']);totals['allWayReferences']+=n;totals['allWayPrimitiveEdges']+=n-1
            if 'highway' not in row['tags']:
                totals['nonHighwayWays']+=1;totals['nonHighwayReferences']+=n;totals['nonHighwayPrimitiveEdges']+=n-1
            else:
                totals['highwayWays']+=1;role=row['tags']['highway'];r=roads.setdefault(role,dict.fromkeys(ROAD,0))
                for key,value in zip(ROAD,(1,n,n-1,2,row['nodes'][0]==row['nodes'][-1],n>1024,0)):r[key]+=value
                r['maxReferences']=max(r['maxReferences'],n)
        if kind=='relation':
            restriction=row['tags'].get('type')=='restriction';totals['restrictionRelations']+=restriction
            for member in row['members']:
                k=member['type'];totals['relation'+k.title()+'Members']+=1
                if restriction:
                    totals['restriction'+k.title()+'Members']+=1
                    restrictions.setdefault(member['role'],dict.fromkeys(('node','way','relation'),0))[k]+=1
    return {'totals':totals,'highwayRoles':roads,'restrictionMemberRoles':restrictions}


class Tests(unittest.TestCase):
    setUp=prior.NativeTests.setUp
    directory=prior.NativeTests.directory
    def engine(self,**kwargs):
        if ARTIFACT is None:self.skipTest('Target Linux compiled footprint helper required')
        return NativeScreen(*ARTIFACT,**kwargs)

    # Reuse the independent frozen validators, not the previous native implementation.
    test_scalar_calendar_order=prior.NativeTests.test_scalar_calendar_order
    test_utf8_duplicates_copy=prior.NativeTests.test_utf8_duplicates_copy
    test_canonical_fallback=prior.NativeTests.test_canonical_fallback
    test_refs_members_xy_receipts=prior.NativeTests.test_refs_members_xy_receipts
    test_callback_failure_reentry_truncation=prior.NativeTests.test_callback_failure_reentry_truncation
    test_fast_node_blocks=prior.NativeTests.test_fast_node_blocks
    test_pbf_fields_framing_epoch=prior.NativeTests.test_pbf_fields_framing_epoch
    test_posthash_source_drift=prior.NativeTests.test_posthash_source_drift
    test_discarded_node_metadata=prior.NativeTests.test_discarded_node_metadata
    test_seeded_float_bits=prior.NativeTests.test_seeded_float_bits
    test_wire_types_reserved_and_copy=prior.NativeTests.test_wire_types_reserved_and_copy
    test_u64_arithmetic=prior.NativeTests.test_real_checked_u64_operations_and_abi_lengths
    pbf=prior.NativeTests.pbf

    def test_exact_all_roles_profiles_long_closed_ways_and_semantic_identity(self):
        rows=fixture();expected=oracle(rows)
        for proof in (False,True):
            receipt=self.engine().validate_frames(framed_records(rows),STATE,self.caps,proof=proof)
            self.assertEqual(receipt['histogram'],expected)
            self.assertEqual(receipt['semanticSha256'],reference_seal(rows))
            self.assertTrue(reconcile(expected,receipt));self.assertEqual(receipt['pythonProjectionFrames'],len(rows) if proof else 0)
            self.assertEqual(receipt['callbackEvents'][9],1)
        major=profile(expected['highwayRoles'],MAJOR)
        self.assertEqual(major['ways'],13);self.assertEqual(major['longWays'],1)

    def test_actual_pbf_exact_histogram_and_complete_source_guards(self):
        rows=fixture();receipt=self.engine().scan(self.pbf(rows),STATE,self.caps)
        self.assertEqual(receipt['histogram'],oracle(rows));self.assertTrue(receipt['nativeEof'])
        self.assertEqual(receipt['semanticSha256'],reference_seal(rows));self.assertEqual(receipt['pythonProjectionFrames'],0)

    def test_empty_input_has_zero_counts_and_histogram(self):
        receipt=self.engine().validate_frames(b'',STATE,self.caps)
        self.assertEqual(receipt['histogram'],oracle([]));self.assertTrue(receipt['nativeEof'])

    def test_dictionary_key_and_cardinality_caps_stop_without_eof(self):
        for roles in (['x'*4097],[str(i) for i in range(4097)]):
            base=fixture_records()[4];rows=[dict(base,id=i+1,tags={'highway':role}) for i,role in enumerate(roles)]
            engine=self.engine()
            with self.assertRaisesRegex(PilotError,'histogram_'):engine.validate_frames(framed_records(rows),STATE,self.caps)
            self.assertFalse(engine.last['nativeEof'])

    def test_counter_tampering_and_binary_corruption_are_rejected(self):
        receipt=self.engine().validate_frames(framed_records(fixture()),STATE,self.caps)
        for field in TOTALS:
            bad=deepcopy(receipt['histogram']);bad['totals'][field]+=10**9
            with self.assertRaises(PilotError):reconcile(bad,receipt)
        for raw in (b'',b'GPH1',b'GPH0'+b'\0'*160,b'GPH1'+b'\0'*160+b'x'):
            with self.assertRaises(PilotError):decode_histogram(raw)

    def test_storage_bounds_use_full_reference_denominator_and_no_ratio(self):
        histogram=oracle(fixture());bounds=storage_bounds(histogram)
        for key,roles in (('all-highways',None),('major-roads',MAJOR)):
            selected=[row for row in fixture() if row['type']=='way' and 'highway' in row['tags'] and (roles is None or row['tags']['highway'] in roles)]
            refs=sum(len(row['nodes']) for row in selected);edges=sum(len(row['nodes'])-1 for row in selected)
            self.assertEqual(bounds[key]['degreeRecordSpoolBytes'],16*refs)
            self.assertEqual(bounds[key]['routingAndGeometryUpperBytes'],20*refs+36*edges+8)

    def test_callback_deadline_and_aggregate_budget_stop(self):
        engine=self.engine(aggregate_visits=2)
        with self.assertRaises(PilotError):engine.validate_frames(framed_records(fixture_records()),STATE,self.caps)
        self.assertFalse(engine.last['nativeEof'])
        def expired():raise PilotError('fixture deadline')
        with self.assertRaisesRegex(PilotError,'fixture deadline'):self.engine().validate_frames(b'',STATE,self.caps,check=expired)


class ControllerTests(unittest.TestCase):
    def test_exclusive_output_rejects_overwrite_escape_symlink_and_size(self):
        import tempfile
        from pathlib import Path
        from run_osm_footprint_v1 import bounded_save
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);bounded_save(root,'result.json',{'ok':True})
            (root/'link').symlink_to(root/'missing')
            for key,value in (('result.json',{}),('../escape',{}),('link',{}),('big','x'*2097152)):
                with self.assertRaises(PilotError):bounded_save(root,key,value)

    def test_cleanup_refuses_unrelated_worker(self):
        import json,subprocess,tempfile
        from pathlib import Path
        from prepare_osm_native_lock_v1 import IMAGE,cleanup_owned,settle_error
        calls=[]
        def call(args):
            calls.append(args)
            return subprocess.CompletedProcess(args,0,json.dumps([{'Id':'a','Image':IMAGE,'Config':{'Labels':{}},'State':{'Running':True}}]),'')
        with tempfile.TemporaryDirectory() as name:
            for action in (lambda:settle_error(call,None,'name','owner',Path(name),None),lambda:cleanup_owned(call,None,'name','owner',IMAGE,Path(name))):
                with self.assertRaises(PilotError):action()
        self.assertTrue(all(c[1]=='inspect' for c in calls))

    def test_resource_isolation_checks_memory_swap_network_mounts_and_caps(self):
        from run_osm_footprint_v1 import IMAGE,CAPS,isolation
        observed={'Image':IMAGE,'Mounts':[{'Destination':'/code/test.py','RW':False}],
            'HostConfig':{'NetworkMode':'none','Memory':4294967296,'MemorySwap':4294967296,'ReadonlyRootfs':True,'NanoCpus':2000000000,'PidsLimit':64,'Tmpfs':{'/tmp':'rw,size=256m'},'CapAdd':None,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],'Ulimits':[{'Name':'core','Soft':0,'Hard':0},{'Name':'fsize','Soft':67108864,'Hard':67108864}]}}
        isolation(observed,'controls')
        for key,value in (('NetworkMode','bridge'),('MemorySwap',8589934592),('Memory',8589934592),('CapAdd',['SYS_ADMIN'])):
            bad=deepcopy(observed);bad['HostConfig'][key]=value
            with self.assertRaises(PilotError):isolation(bad,'controls')
        bad=deepcopy(observed);bad['Mounts'][0]['RW']=True
        with self.assertRaises(PilotError):isolation(bad,'controls')

    def test_recipe_refuses_source_caps_admission_and_extra_source_mounts(self):
        from run_osm_footprint_v1 import IMAGE,CAPS,SOURCE,SCAN,FLAGS,ASSET_ROOT,HEADERS,OUTPUTS,validate
        plan={'stage':'build','phase':'native_national_footprint_v1','caps':deepcopy(CAPS),'source':deepcopy(SOURCE),'scanCaps':deepcopy(SCAN),'image':IMAGE,'flags':FLAGS,'output':OUTPUTS['build'],'network':'none','imagePull':'never','mounts':{},'inputs':{},'rootfs':{'path':ASSET_ROOT},'headers':{k:{'path':v} for k,v in HEADERS.items()},'assetProof':'docs/evidence/coarse-osm-native-build-2026-10-27/asset_contents.py','site':'data/coarse-quality/us-osm-tools-v3/offline/site','runtime':{}}
        validate(plan)
        for field in ('caps','source','scanCaps'):
            bad=deepcopy(plan);bad[field]={}
            with self.assertRaises(PilotError):validate(bad)
        bad=deepcopy(plan);bad['mounts'][SOURCE['path']]='/inputs/country.pbf';bad['inputs'][SOURCE['path']]=SOURCE['sha256']
        with self.assertRaises(PilotError):validate(bad)
