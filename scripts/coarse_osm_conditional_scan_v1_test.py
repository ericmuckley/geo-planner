"""Independent changed metadata audit and complete-source lifecycle guards."""
from pathlib import Path
import tempfile
import unittest
from coarse_osm_conditional_census_v1 import COUNTERS
import coarse_osm_conditional_census_v1_test as fixtures
from coarse_osm_conditional_scan_v1 import audit,collect
from coarse_timing_input import PilotError


def counters(raw,rows):
    v={k:0 for k in COUNTERS};v.update(changedRecords=len(rows),changedEncodedBytes=len(raw),complete=1)
    for kind,tags in rows:
        v['changedNodeFlags' if kind==0 else 'newlyEligibleWays']+=1
        if kind==1:v['newSpeedConditionalWays']+=1
        v['changedTagUtf8Bytes']+=sum(len(k.encode())+len(x.encode()) for k,x in tags)
    return v


class Tests(unittest.TestCase):
    def test_all_changed_node_and_way_raw_tags_independently_accounted(self):
        rows=[(0,(('hgv:conditional','no @ night'),)),(1,(('highway','primary'),('maxspeed:conditional','20 @ 雪')))]
        raw=b''.join(fixtures.RecordTests.encoded(kind,i+1,tags) for i,(kind,tags) in enumerate(rows))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'records';p.write_bytes(raw);r=audit(p,counters(raw,rows),lambda:None)
            self.assertEqual(r['counts']['nodes'],1);self.assertEqual(r['counts']['ways'],1);self.assertTrue(r['allOldPositiveDecisionsRetained'])

    def test_missing_counts_bytes_or_old_positive_retention_refused(self):
        tags=(('highway','primary'),('maxspeed:conditional','20 @ wet'));raw=fixtures.RecordTests.encoded(tags=tags)
        c=counters(raw,[(1,tags)])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'records';p.write_bytes(raw)
            for changes in ({'changedRecords':0},{'changedEncodedBytes':0},{'newlyEligibleWays':0},{'oldEligibleWays':1},{'oldUnblockedNodes':1}):
                with self.assertRaises(PilotError):audit(p,c|changes,lambda:None)

    def test_native_output_cannot_claim_an_unchanged_or_still_closed_record(self):
        for tags in ((('highway','primary'),),(('highway','primary'),('maxspeed:conditional','none @ wet'))):
            raw=fixtures.RecordTests.encoded(tags=tags)
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'records';p.write_bytes(raw)
                with self.assertRaises(PilotError):audit(p,counters(raw,[(1,tags)]),lambda:None)

    def test_source_identity_count_eof_and_projection_checks_always_release(self):
        class Engine:
            def __init__(self,receipt):self.receipt=receipt;self.released=False
            def begin(self,p):p.write_bytes(b'')
            def scan(self,*args,**kwargs):return self.receipt
            def finish(self):return counters(b'',[])
            def release(self):self.released=True
        good={'nativeEof':True,'counts':{'node':1},'semanticSha256':'seal','pythonProjectionFrames':0}
        with tempfile.TemporaryDirectory() as tmp:
            for i,change in enumerate(({}, {'nativeEof':False},{'counts':{}},{'semanticSha256':'bad'},{'pythonProjectionFrames':1})):
                e=Engine(good|change);p=Path(tmp)/str(i)
                if change:
                    with self.assertRaises(PilotError):collect(e,None,None,None,None,{'node':1},'seal',p,lambda:None)
                else:
                    # Empty changed output still requires complete source counters.
                    e.finish=lambda:counters(b'',[])|{'nodes':1}
                    self.assertEqual(collect(e,None,None,None,None,{'node':1},'seal',p,lambda:None)['independentChangedTagAudit']['counts']['ways'],0)
                self.assertTrue(e.released)
