"""Aggregation equivalence and bounded retention for streamed detailed results."""
from copy import deepcopy
import json
import unittest

from coarse_osm_continuous_match_v1 import summary
from coarse_osm_continuous_match_v1_test import run,short_connector
from run_osm_continuous_match_v2 import summary_record


class Tests(unittest.TestCase):
    def test_actual_synthetic_candidates_keep_identical_aggregates(self):
        records=[run(),run(short_connector()),run(short_connector(False))]
        self.assertEqual(summary(records),summary([summary_record(r) for r in records]))
        for source_class in (85,105):
            selected=[r for r in records if r['sourceClassKph']==source_class]
            self.assertEqual(summary(selected),summary([summary_record(r) for r in selected]))

    def test_large_written_payload_is_not_retained_or_mutated(self):
        record=run();record['fragmentIssues']=['x'*1000]*1000;record['candidates'][0]['variants']=[{'large':'x'*1000}]*1000
        before=deepcopy(record);small=summary_record(record)
        self.assertLess(len(json.dumps(small)),512);self.assertEqual(record,before)
        self.assertEqual(summary([small]),summary([record]));self.assertNotIn('variants',small['candidates'][0]);self.assertNotIn('fragmentIssues',small)

    def test_capped_multiple_and_empty_outcomes_preserve_every_weight(self):
        seed=run();records=[]
        for i,status in enumerate(('projection_cap','search_capped','multiple_acquired_file_geometric_paths','no_path_under_fragment_rules')):
            r=deepcopy(seed);r.update(status=status,sourceKm=i+1.,sourceClassKph=85 if i%2 else 105,searchCapped=i<2);records.append(r)
        small=[summary_record(r) for r in records]
        self.assertEqual(summary(small),summary(records));self.assertEqual(sum(r['sourceKm'] for r in small),10);self.assertEqual(sum(r['searchCapped'] for r in small),2)
