"""Synthetic controls for the frozen sample adapter; no saved sample is opened."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import unittest

import coarse_osm_projector_v1_test as prior
from coarse_osm_projector_v1 import framed_records,field_frame
from coarse_osm_sample_v1 import (Visits,run_case,encode_mixed,source_start,source_end,CAPS,config,SAMPLES)
from coarse_osm_records import canonical
from coarse_osm_stream_v1 import NativeValidator
from coarse_osm_native_smoke import fixture_records,STATE
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    setUp=prior.Tests.setUp
    directory=prior.Tests.directory
    pbf=prior.Tests.pbf
    engine=prior.Tests.engine

    def test_budget_exact_limit_and_case_configuration(self):
        visits=Visits(2);visits.check(2);self.assertEqual(visits.total,0);visits.add(2)
        with self.assertRaises(PilotError):visits.add()
        self.assertEqual(visits.total,2)
        changed=config(self.config);self.assertEqual(changed['proposedCaps']['scanNodesPerPass'],200000)
        self.assertEqual(self.caps['scanNodesPerPass'],10000)

    def test_source_postcheck_is_full_content_and_immutable_file(self):
        # Host-only control uses an opaque file for post-hash integrity, no PBF decoder.
        path=self.root/'opaque';path.write_bytes(b'abc');stat=path.stat()
        before=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
        identity={'sourceSha256':hashlib.sha256(b'abc').hexdigest()}
        result=source_end(path,before,identity,lambda:None);self.assertEqual(result['postSourceHashBytes'],3)
        path.write_bytes(b'abd');os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
        with self.assertRaises(PilotError):source_end(path,before,identity,lambda:None)
        path.unlink();path.symlink_to(self.root/'missing')
        with self.assertRaises(PilotError):source_start(path,self.caps,STATE,lambda:None)

    def test_case_watchdog_kills_a_worker_without_python_callbacks(self):
        scripts=str(Path(__file__).resolve().parent)
        code='import sys,time;sys.path.insert(0,sys.argv[1]);from coarse_osm_sample_v1 import case_deadline\nwith case_deadline(.05):time.sleep(5)'
        child=subprocess.run([sys.executable,'-B','-c',code,scripts],capture_output=True,timeout=5)
        self.assertEqual(child.returncode,-9,child.stderr)

    def test_seeded_native_float_bits_and_exact_near_caps_match_reference(self):
        engine=self.engine();rng=random.Random(20261027);base=fixture_records()[0]
        values=[(-1800000000,-900000000),(1800000000,900000000),(-1,1),(0,0)]
        values.extend((rng.randrange(-1800000000,1800000001),rng.randrange(-900000000,900000001)) for _ in range(24))
        for k,(x,y) in enumerate(values):
            row=dict(base,id=2**63-1 if k==0 else k+1,lon=x/10000000,lat=y/10000000,tags={'text':'é😀\x7f"\\'*24} if k%2 else {})
            size=len(canonical(row))
            for limit in (size-1,size,size+1):
                reference=NativeValidator(STATE,limit,self.caps,lambda raw,line:None)
                try:reference.see(prior.NativeView(row));accepted=True
                except Exception:accepted=False
                actual=[]
                try:engine.validate_frames(framed_records([row]),STATE,dict(self.caps,singleNormalizedElementBytes=limit),proof=True,on_record=actual.append);passed=True
                except Exception:passed=False
                self.assertEqual(passed,accepted,(k,limit))
                if passed:self.assertEqual(struct.pack('<dd',actual[0]['lon'],actual[0]['lat']),struct.pack('<dd',row['lon'],row['lat']))
        for value in (-0.,float('inf'),float('nan'),.123456789):
            with self.assertRaises(PilotError):framed_records([dict(base,lon=value)])

    def test_native_wire_unknown_type_member_reserved_and_copy_bounds(self):
        engine=self.engine();node=field_frame(dict(fixture_records()[0],tags={}))
        variants=[]
        for offset,value in ((4,3),(5,2),(6,1)):
            body=bytearray(node);body[offset]=value;variants.append(body)
        body=bytearray(node);body[48:52]=struct.pack('<I',2**32-1);variants.append(body)
        relation=dict(fixture_records()[7],tags={},members=[{'type':'node','ref':1,'role':''}])
        body=bytearray(field_frame(relation));body[56]=255;variants.append(body)
        for body in variants:
            with self.assertRaises(PilotError):engine.validate_frames(struct.pack('<I',len(body))+bytes(body),STATE,self.caps)
            self.assertFalse(engine.last['nativeEof'])
        for row,limit in ((dict(fixture_records()[4],tags={},nodes=[1]*20),895),
            (dict(relation,members=[{'type':'node','ref':1,'role':'abc'}]),386)):
            with self.assertRaises(PilotError):engine.validate_frames(framed_records([row]),STATE,dict(self.caps,singleNormalizedElementBytes=limit))

    def test_paired_source_io_fields_and_same_index_lookup_policy(self):
        engine=self.engine();rows=fixture_records()[:4];path=self.pbf(rows);budget=Visits();proofs=[]
        for mode in ('python','native'):
            folder=self.directory()/'proof'
            kwargs={'expected':self.root/'reference.jsonl'} if mode=='native' else {}
            result=run_case(path,self.config,folder,engine=engine,budget=budget,mode=mode,proof=True,source_sha=hashlib.sha256(path.read_bytes()).hexdigest(),**kwargs)
            if mode=='python':(self.root/'reference.jsonl').write_bytes((folder/'fields.jsonl').read_bytes())
            proofs.append(result)
            self.assertEqual(result['coordinateRowsProved'],4);self.assertEqual(result['framingBytesRead'],path.stat().st_size)
            self.assertEqual(result['knownGuardReadBytes'],2*path.stat().st_size)
            self.assertGreaterEqual(result['protectedTotalSeconds'],result['decodeValidateIndexSealEofSeconds']+result['framingSeconds']+result['postSourceHashSeconds'])
        self.assertEqual(proofs[0]['canonicalSha256'],proofs[1]['canonicalSha256']);self.assertEqual(proofs[0]['semanticSha256'],proofs[1]['semanticSha256'])
        paired=[run_case(path,self.config,self.directory()/'fast',engine=engine,budget=budget,mode=mode,queries=[4,1,1]) for mode in ('python','native')]
        self.assertEqual(paired[0]['indexBytes'],paired[1]['indexBytes']);self.assertEqual(paired[1]['receipt']['pythonProjectionFrames'],0)
        self.assertEqual({v['coordinateBitsSha256'] for p in paired for v in p['lookup']},{paired[0]['lookup'][0]['coordinateBitsSha256']})
        self.assertTrue(all(v['authenticatedShardBytesRead']>0 for p in paired for v in p['lookup']))
        self.assertEqual(budget.total,16)

    def test_full_field_oracle_failure_and_source_binding_cannot_claim_eof(self):
        engine=self.engine();path=self.pbf();oracle=self.root/'wrong.jsonl';oracle.write_bytes(b'{}\n')
        for options in ({'expected':oracle},{'source_sha':'0'*64}):
            folder=self.directory()/'bad'
            with self.assertRaises(PilotError):run_case(path,self.config,folder,engine=engine,budget=Visits(),mode='native',proof=True,**options)
            state=json.loads((folder/'partial-result.json').read_text());self.assertFalse(state['eof']);self.assertFalse(state['indexesTrusted'])

    def test_mixed_encoding_preserves_fields_and_unresolved_references(self):
        engine=self.engine();rows=fixture_records();source=self.root/'records.jsonl';source.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
        budget=Visits();target=self.root/'mixed.pbf';result=encode_mixed(source,target,budget,{'node':4,'way':3,'relation':2})
        self.assertEqual(result['records'],9);self.assertEqual(budget.total,18)
        actual=[];engine.scan(target,STATE,self.caps,proof=True,on_record=actual.append);self.assertEqual(actual,rows)
        self.assertEqual(actual[-2]['members'][-1]['ref'],999)

    def test_sample_plan_refuses_national_mount_or_resource_drift(self):
        from run_osm_sample_v1 import validate,ARTIFACT
        from run_osm_sample_v1 import layout
        # Real hash/mount closure is checked by the frozen runner; this control targets paths/caps.
        mounts={'scripts/coarse_osm_sample_v1.py':'/code/coarse_osm_sample_v1.py'}
        plan={'phase':'controls','caps':CAPS,'output':layout('controls'),'imageId':'sha256:1618ba836b700c8bf3daa2637e0949a323724bfca49b751a4ff4614295da9402',
            'imagePull':'never','network':'none','artifact':__import__('coarse_osm_sample_v1').ARTIFACT,'samples':SAMPLES,'cases':__import__('coarse_osm_sample_v1').CASES,
            'mounts':mounts,'inputs':{'scripts/coarse_osm_sample_v1.py':'x',ARTIFACT['path']:ARTIFACT['sha256']},
            'workerFiles':{'/code/coarse_osm_sample_v1.py':'x','/artifacts/projector.so':ARTIFACT['sha256']},'sampleWorkerFiles':{}}
        validate(plan)
        for change in ({'output':'data/other'},{'phase':'build'},{'caps':dict(CAPS,caseSeconds=61)},{'samples':{}}):
            with self.assertRaises(PilotError):validate(plan|change)
        bad=deepcopy(plan);bad['mounts']['data/national.pbf']='/samples/source.pbf'
        with self.assertRaises(PilotError):validate(bad)


if __name__=='__main__':unittest.main()
