"""Independent changed-tag accounting, source guards and failure release."""
from pathlib import Path
import tempfile
import unittest

import coarse_osm_conditional_census_v1_test as wire
from coarse_osm_explicit_lane_census_v1 import COUNTERS
from coarse_osm_explicit_lane_census_v1_test import lane
from coarse_osm_explicit_lane_scan_v1 import audit,collect
from coarse_timing_input import PilotError


def fixture(path,kind=1,tags=None):
    tags=lane() if tags is None else tags
    raw=wire.RecordTests.encoded(kind,1,tuple(sorted(tags.items())));path.write_bytes(raw)
    c={key:0 for key in COUNTERS};c.update(newlyEligibleWays=1,newLaneWaysWithoutSpeedConditional=1,changedRecords=1,
        changedEncodedBytes=len(raw),changedTagUtf8Bytes=sum(len(k.encode())+len(v.encode()) for k,v in tags.items()),
        majorWays=1,allMajorWayPoliciesCompared=1,laneRejectedWays=1,complete=1)
    return c


class Tests(unittest.TestCase):
    def test_every_changed_way_and_byte_independently_accounted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'records';c=fixture(path);r=audit(path,c,lambda:None)
            self.assertEqual(r['counts']['ways'],1);self.assertTrue(r['allOldPositiveDecisionsRetained'])

    def test_counter_disagreement_and_old_positive_loss_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'records';c=fixture(path)
            for change in ({'changedRecords':0},{'changedEncodedBytes':0},{'newlyEligibleWays':0},
                           {'oldEligibleWays':1},{'oldUnblockedNodes':1},{'nodes':1},{'majorWays':2},
                           {'changedNodeFlags':1},{'laneFallbackWays':1}):
                with self.assertRaises(PilotError):audit(path,c|change,lambda:None)

    def test_unchanged_restricted_ambiguous_or_node_records_refused(self):
        for kind,tags in ((1,{'highway':'primary'}),(1,lane(oneway='no')),(1,lane(**{'motor_vehicle:lanes':'|yes|yes'})),(0,lane())):
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'records';c=fixture(path,kind,tags)
                with self.assertRaises(PilotError):audit(path,c,lambda:None)

    def test_source_receipt_identity_eof_counts_and_projections_always_release(self):
        class Engine:
            def __init__(self,receipt):self.receipt=receipt;self.released=False
            def begin(self,p):p.write_bytes(b'')
            def scan(self,*args,**kwargs):return self.receipt
            def finish(self):return {key:int(key in ('nodes','allNodeFlagsExact')) for key in COUNTERS}
            def release(self):self.released=True
        good={'nativeEof':True,'counts':{'node':1},'semanticSha256':'seal','pythonProjectionFrames':0}
        with tempfile.TemporaryDirectory() as tmp:
            for index,change in enumerate(({}, {'nativeEof':False},{'counts':{}},{'semanticSha256':'bad'},{'pythonProjectionFrames':1})):
                engine=Engine(good|change);path=Path(tmp)/str(index)
                if change:
                    with self.assertRaises(PilotError):collect(engine,None,None,None,None,{'node':1},'seal',path,lambda:None)
                else:self.assertEqual(collect(engine,None,None,None,None,{'node':1},'seal',path,lambda:None)['independentChangedTagAudit']['counts']['ways'],0)
                self.assertTrue(engine.released)

    def test_byte_change_with_original_mtime_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'records';c=fixture(path);before=path.stat();changed=False
            def mutate():
                nonlocal changed
                if changed:return
                changed=True;path.write_bytes(path.read_bytes().replace(b'no|yes|yes',b'no|yes|no|'))
                os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            with self.assertRaises((PilotError,AssertionError)):audit(path,c,mutate)

    def test_checkpoint_precedes_independent_audit_failure(self):
        class Engine:
            def begin(self,p):p.write_bytes(b'')
            def scan(self,*args,**kwargs):return {'nativeEof':True,'counts':{'node':1},'semanticSha256':'seal','pythonProjectionFrames':0}
            def finish(self):return {key:int(key in ('nodes','allNodeFlagsExact','changedRecords')) for key in COUNTERS}
            def release(self):self.released=True
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine();saved=[]
            with self.assertRaises(PilotError):collect(engine,None,None,None,None,{'node':1},'seal',Path(tmp)/'out',lambda:None,saved.append)
            self.assertTrue(engine.released);self.assertEqual(len(saved),1)
            self.assertEqual(saved[0]['explicitLanes']['nodes'],1)
