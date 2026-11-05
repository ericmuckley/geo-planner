"""Independent changed metadata audit and complete-source lifecycle guards."""
from pathlib import Path
import tempfile
import unittest
from coarse_osm_conditional_census_v1 import COUNTERS
import coarse_osm_conditional_census_v1_test as fixtures
from coarse_osm_conditional_scan_v2 import audit,collect
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


class StabilityRegressionTests(unittest.TestCase):
    def fixture(self,root):
        tags=(('highway','primary'),('maxspeed:conditional','20 @ wet'))
        raw=fixtures.RecordTests.encoded(tags=tags);path=root/'records';path.write_bytes(raw)
        return path,counters(raw,[(1,tags)])

    def test_access_time_change_reproduces_v1_stop_but_v2_preserves_source_identity(self):
        import os
        from coarse_osm_conditional_scan_v1 import audit as old_audit
        with tempfile.TemporaryDirectory() as tmp:
            path,c=self.fixture(Path(tmp))
            def access_only():
                s=path.stat();os.utime(path,ns=(s.st_atime_ns+60000000000,s.st_mtime_ns))
            with self.assertRaisesRegex(PilotError,'bytes/stat stable'):old_audit(path,c,access_only)
            result=audit(path,c,access_only)
            self.assertEqual(result['counts']['ways'],1)

    def test_byte_change_with_original_mtime_cannot_pass_hash_checks(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            path,c=self.fixture(Path(tmp));before=path.stat();changed=False
            def change_once():
                nonlocal changed
                if changed:return
                changed=True;raw=path.read_bytes();path.write_bytes(raw.replace(b'20 @ wet',b'30 @ wet'))
                os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            with self.assertRaisesRegex(PilotError,'bytes/stat stable'):audit(path,c,change_once)

    def test_source_receipt_and_counters_checkpoint_precedes_audit_failure(self):
        class Engine:
            def begin(self,p):p.write_bytes(b'')
            def scan(self,*args,**kwargs):return {'nativeEof':True,'counts':{'node':1},'semanticSha256':'seal','pythonProjectionFrames':0}
            def finish(self):return counters(b'',[])|{'nodes':1,'changedRecords':1}
            def release(self):self.released=True
        with tempfile.TemporaryDirectory() as tmp:
            e=Engine();saved=[]
            with self.assertRaises(PilotError):collect(e,None,None,None,None,{'node':1},'seal',Path(tmp)/'out',lambda:None,saved.append)
            self.assertTrue(e.released);self.assertEqual(len(saved),1)
            self.assertTrue(saved[0]['receipt']['nativeEof']);self.assertEqual(saved[0]['conditional']['nodes'],1)
