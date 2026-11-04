from pathlib import Path
import tempfile
import unittest

from analyze_osm_water_excluded_bounds_v1 import analyze,dependencies
from assemble_osm_water_polygons_v1 import assemble
from coarse_osm_water_catalog_v1 import WaterCatalog
from prepare_osm_water_catalog_v1 import load_catalog
from prepare_osm_water_catalog_v1_test import fixture

ARTIFACT=None
COORDINATE_ARTIFACT=None


class BoundsControls(unittest.TestCase):
    def test_nested_dependency_union_and_explicit_absent_relation(self):
        row=lambda members:{'members':members}
        way=lambda i:{'type':'way','ref':i}
        relation=lambda i:{'type':'relation','ref':i}
        records={1:row([way(10),relation(2),relation(99)]),2:row([way(20),way(10),relation(1)])}
        self.assertEqual(dependencies(1,records),([10,20],[99]))

    def test_tiny_complete_exclusion_bounds_and_unlocatable_missing_geometry(self):
        if ARTIFACT is None or COORDINATE_ARTIFACT is None:self.skipTest('Qualified Linux catalog/coordinate artifacts required')
        catalog=WaterCatalog(*ARTIFACT);catalog.release()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);references,coordinates,members,endroot,endpoints=fixture(root)
                _,ids,counts=load_catalog(catalog,COORDINATE_ARTIFACT,root,references,root,coordinates)
                out=root/'out';out.mkdir();polygons={'polygons':assemble(out,catalog,ids,counts,members,endroot,endpoints)}
                result=analyze(catalog,ids,counts,members,endroot,endpoints,out,polygons,root/'tiny-roots.gz',root/'tiny-desc.gz',[[0.000021,0],[0,0]])
                self.assertEqual((result['excludedStandaloneWays'],result['excludedRootRelations']),(1,1))
                self.assertEqual(result['excludedFeatures'][0]['knownSourceBoundsE7'],[200,0,220,0])
                self.assertTrue(result['excludedFeatures'][0]['allReferencedSourceGeometryBounded'])
                self.assertEqual(result['queries'][0]['overlappingKnownExcludedSourceBounds'],[{'kind':1,'id':40,'allReferencedSourceGeometryBounded':True}])
                self.assertEqual(result['queries'][1]['overlappingKnownExcludedSourceBounds'],[])
                self.assertEqual(result['unboundedOrSourceIncompleteFeatures'][0]['missingSourceWayIds'],[999])
        finally:catalog.release()


if __name__=='__main__':unittest.main()
