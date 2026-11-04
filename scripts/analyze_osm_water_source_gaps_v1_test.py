import unittest
from analyze_osm_water_source_gaps_v1 import summarize


def row(identity,ways=(),relations=()):
    return {'id':identity,'tags':{'type':'multipolygon'},'members':
            [{'type':'way','ref':i,'role':'outer'} for i in ways]+[{'type':'relation','ref':i,'role':'inner'} for i in relations]}


class Controls(unittest.TestCase):
    def test_transitive_way_and_relation_gaps_reach_only_ancestors(self):
        records=[(True,row(1,relations=[2])),(False,row(2,ways=[99])),(True,row(3,relations=[6])),(True,row(4,ways=[10]))]
        result=summarize(lambda:iter(records),{99},{6})
        self.assertEqual(result['affectedRootsAndReasonBits'],[[1,1],[3,2]])
        self.assertEqual(result['directRootSourceGapCount'],1)

    def test_cycle_with_known_gap_propagates_and_terminates(self):
        records=[(True,row(1,relations=[2])),(False,row(2,ways=[99],relations=[1]))]
        self.assertEqual(summarize(lambda:iter(records),{99},set())['affectedRootsAndReasonBits'],[[1,1]])

    def test_all_available_has_no_invented_gap(self):
        records=[(True,row(1,ways=[10],relations=[2])),(False,row(2,ways=[20]))]
        self.assertEqual(summarize(lambda:iter(records),set(),set())['rootsDependingOnAnyKnownSourceGap'],0)

    def test_missing_id_parity_and_duplicates_are_required(self):
        records=[(True,row(1,ways=[99],relations=[6]))]
        for ways,relations in [({98},{6}),({99},{7})]:
            with self.assertRaises(Exception):summarize(lambda:iter(records),ways,relations)
        with self.assertRaises(Exception):summarize(lambda:iter(records+records),{99},{6})


if __name__=='__main__':unittest.main()
