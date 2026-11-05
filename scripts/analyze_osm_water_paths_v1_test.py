"""Unknown source attributes cannot become defaults or silently disappear."""
import unittest
from analyze_osm_water_paths_v1 import source_exposure


class ExposureTests(unittest.TestCase):
    def test_partial_and_unknown_costs_remain_distinct(self):
        record={'road':{'steps':[{'arc':1,'ticks':8,'portion':'full'},{'arc':2,'ticks':4,'portion':'source-suffix'},{'arc':3,'ticks':7,'portion':'full'}]},'components':{'roadTravelTicks':19}}
        attributes={'1':{'defaultSpeed':True,'role':'tertiary','sourceFullCostTicks':8},'2':{'defaultSpeed':False,'role':'primary','sourceFullCostTicks':20}}
        r=source_exposure(record,attributes)
        self.assertEqual((r['explicitTicks'],r['defaultTicks'],r['unknownTicks']),(4,8,7));self.assertEqual(r['fullArcCostChecks'],1)
        self.assertEqual(r['unknownArcs'],['3'])
        attributes['1']['sourceFullCostTicks']=9
        with self.assertRaises(AssertionError):source_exposure(record,attributes)

    def test_zero_road_path_has_no_assumed_source_exposure(self):
        r=source_exposure({'road':None,'components':{'roadTravelTicks':0}},{});self.assertEqual(r['knownArcs'],[]);self.assertEqual(r['unknownTicks'],0)


if __name__=='__main__':unittest.main()
