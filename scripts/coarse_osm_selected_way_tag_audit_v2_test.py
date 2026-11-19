"""Independent complete-denominator and eligibility checks for original way tags."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from coarse_osm_selected_way_tag_audit_v1 import audit as original_audit

from coarse_osm_conditional_census_v1_test import RecordTests
from coarse_osm_selected_way_tag_audit_v2 import audit
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def run_audit(self, records, selected, mutate=None):
        raw = b''.join(RecordTests.encoded(kind=1,identity=i,tags=tuple(sorted(tags.items()))) for i,tags in records)
        counters = dict(requestedWays=len(selected),selectedRecords=len(records),encodedBytes=len(raw),
                        tagUtf8Bytes=sum(len(k.encode())+len(v.encode()) for _,tags in records for k,v in tags.items()))
        if mutate: mutate(counters)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tags';path.write_bytes(raw)
            return audit(path,counters,selected,lambda:None)
    def selection(self, identity=1, eligible=False):
        return {identity:dict(sourceWay=identity,storedSourceFlags=0,baseEligible=eligible,finalFallbackClosed=eligible)}
    def test_base_access_and_independent_fallback_are_separate(self):
        selected=self.selection() | self.selection(2,True)
        result=self.run_audit([(1,{'highway':'primary','access':'private'}),(2,{'highway':'primary'})],selected)
        self.assertEqual(result['currentBaseReasonCounts'],{'access':1,'None':1})
        self.assertTrue(result['wayEvidence']['2']['finalFallbackClosed'])
        self.assertEqual(result['unknownRawWayIds'],[])
    def test_missing_extra_or_unexplained_eligibility_rejected(self):
        for records in ([],[(2,{'highway':'primary','access':'private'})],[(1,{'highway':'primary'})]):
            with self.assertRaises(PilotError):self.run_audit(records,self.selection())
    def test_every_counter_must_match(self):
        for key in ('requestedWays','selectedRecords','encodedBytes','tagUtf8Bytes'):
            with self.assertRaises(PilotError):self.run_audit([(1,{'highway':'primary','access':'private'})],self.selection(),lambda c:c.update({key:c[key]+1}))
    def test_large_native_identity_is_exact(self):
        identity=2**53+1
        result=self.run_audit([(identity,{'highway':'primary','access':'private'})],self.selection(identity))
        self.assertEqual(result['wayEvidence'][str(identity)]['sourceWay'],identity)
    def test_lane_unknowns_and_explicit_permission_are_not_inferred(self):
        result=self.run_audit([(1,{'highway':'motorway','access:lanes':'yes|designated','hov:lanes':'designated|yes'})],self.selection())
        self.assertIsNotNone(result['wayEvidence']['1']['currentRawPolicy']['reason'])
        self.assertFalse(result['routingOrAccuracyAccepted'])

    def test_access_time_changes_alone_are_not_content_drift(self):
        raw=RecordTests.encoded(kind=1,identity=1,tags=(('access','private'),('highway','primary')))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tags';path.write_bytes(raw);before=path.stat();calls=0
            def observed(p, *args, **kwargs):
                nonlocal calls
                calls+=1
                fields={k:getattr(before,k) for k in dir(before) if k.startswith('st_')}
                fields.update(st_atime=before.st_atime+calls,st_atime_ns=before.st_atime_ns+calls)
                return SimpleNamespace(**fields)
            counters=dict(requestedWays=1,selectedRecords=1,encodedBytes=len(raw),tagUtf8Bytes=27)
            # These bytes include keys and values: access/private/highway/primary.
            counters['tagUtf8Bytes']=6+7+7+7
            with patch.object(Path,'stat',observed):
                with self.assertRaisesRegex(PilotError,'output stable'):original_audit(path,counters,self.selection(),lambda:None)
            with patch.object(Path,'stat',observed):
                self.assertEqual(audit(path,counters,self.selection(),lambda:None)['selectedWays'],1)

    def test_identity_modification_and_change_times_still_fail(self):
        raw=RecordTests.encoded(kind=1,identity=1,tags=(('access','private'),('highway','primary')))
        for field in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'):
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'tags';path.write_bytes(raw);before=path.stat();calls=0
                def observed(p,*args,**kwargs):
                    nonlocal calls
                    calls+=1;fields={k:getattr(before,k) for k in dir(before) if k.startswith('st_')}
                    # First two stat calls bind the real baseline.
                    if calls>2:fields[field]+=1
                    return SimpleNamespace(**fields)
                counters=dict(requestedWays=1,selectedRecords=1,encodedBytes=len(raw),tagUtf8Bytes=27)
                with patch.object(Path,'stat',observed):
                    with self.assertRaises((PilotError,AssertionError)):audit(path,counters,self.selection(),lambda:None)


if __name__ == '__main__': unittest.main()
