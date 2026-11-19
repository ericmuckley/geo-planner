import tempfile
from pathlib import Path
import unittest

from coarse_osm_conditional_census_v1_test import RecordTests
from coarse_osm_selected_node_tag_audit_v1 import audit
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def check_records(self, records, nodes, contributors, mutate=None):
        raw=b''.join(RecordTests.encoded(kind=0,identity=i,tags=tuple(sorted(tags.items()))) for i,tags in records)
        counters={'requestedNodes':len(nodes),'selectedRecords':len(records),'encodedBytes':len(raw),
                  'tagUtf8Bytes':sum(len(k.encode())+len(v.encode()) for _,tags in records for k,v in tags.items())}
        if mutate:mutate(counters)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tags';path.write_bytes(raw)
            return audit(path,counters,nodes,contributors,lambda:None)

    def test_base_node_and_independent_node_only_causes_both_retained(self):
        result=self.check_records([(1,{'motorcar':'no'}),(2,{})],{1:{'flags':1},2:{'flags':1}},{2:[90]})
        self.assertEqual(result['causeCounts'],{'base-node':1,'restriction-only':1})
        self.assertEqual(result['unknownRawNodeIds'],[])
        self.assertEqual(result['nodeEvidence']['2']['restrictionContributorIds'],[90])

    def test_missing_extra_wrong_and_unexplained_records_rejected(self):
        for records,nodes in (([],{1:{'flags':1}}),([(2,{'motorcar':'no'})],{1:{'flags':1}}),([(1,{})],{1:{'flags':1}})):
            with self.assertRaises(PilotError):self.check_records(records,nodes,{})

    def test_signals_and_each_byte_count_reconcile(self):
        with self.assertRaises(PilotError):self.check_records([(1,{'motorcar':'no'})],{1:{'flags':3}},{})
        for key in ('encodedBytes','tagUtf8Bytes','requestedNodes','selectedRecords'):
            with self.assertRaises(PilotError):
                self.check_records([(1,{'motorcar':'no'})],{1:{'flags':1}},{},lambda c:c.update({key:c[key]+1}))

    def test_large_integer_ids_never_round_through_float(self):
        identity=2**53+1
        result=self.check_records([(identity,{'motor_vehicle':'private'})],{identity:{'flags':5}},{})
        self.assertEqual(result['nodeEvidence'][str(identity)]['sourceNodeId'],str(identity))
