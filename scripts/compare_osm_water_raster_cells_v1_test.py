from pathlib import Path
import tempfile
import unittest

from coarse_osm_water_point_scan_v1_test import geometry
from coarse_osm_water_raster_v1_test import oracle
from compare_osm_water_raster_cells_v1 import compare,segment_touches_box


class CellControls(unittest.TestCase):
    def test_closed_slab_clipping_corners_lines_and_misses(self):
        box=(0,0,10,10)
        for a,b,expected in [((-10,0),(20,0),True),((-10,-10),(0,0),True),((10,0),(10,20),True),((-1,2),(-1,8),False),((-20,11),(20,11),False),((-10,2),(20,8),True)]:
            self.assertEqual(segment_touches_box(a,b,box),expected)

    def fixture(self,root):
        rings=[(0,0,[(0,0),(40,0),(40,40),(0,40),(0,0)]),(1,0,[(10,10),(10,30),(30,30),(30,10),(10,10)])]
        source=geometry(root,[rings]);polygon={'polygons':{'geometryStore':source,'acceptedFeatures':1,'acceptedRings':2,'sourcePointsIndependentlyReplayed':10}}
        feature={'kind':2,'id':99,'knownSourceBoundsE7':[45,5,55,15],'allReferencedSourceGeometryBounded':False}
        exclusion={'exclusions':{'excludedFeatures':[feature],'unboundedOrSourceIncompleteFeatures':[{'kind':2,'id':99,'missingSourceWayIds':[100]}]}}
        grid=(-10,-10,10,8,7);water,uncertain=oracle(grid,[rings],[([45,5,55,15],False)]);observations=[]
        for row in range(7):
            for col in range(8):
                rank=row*8+col
                observations.append({'kind':'cell','phase':'test-center','sourceIndex':rank,'coordinate':[(-10+(col+0.5)*10)/1e7,(-10+(row+0.5)*10)/1e7],
                                     'column':col,'row':row,'waterAtCenter':bool(water[rank//8]&(1<<(rank%8))),'sourceUncertainty':bool(uncertain[rank//8]&(1<<(rank%8)))})
        return polygon,exclusion,grid,observations

    def test_every_small_cell_matches_independent_geometry_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,e,g,o=self.fixture(root);result=compare(root,p,e,g,o)
            self.assertEqual(result['mismatchIndices'],[]);self.assertEqual(len(result['comparisons']),56)
            self.assertEqual(result['unboundedSourceFeaturesRetained'],e['exclusions']['unboundedOrSourceIncompleteFeatures'])

    def test_corrupt_observations_remain_explicit_and_wrong_grid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,e,g,o=self.fixture(root);o[0]['waterAtCenter']=not o[0]['waterAtCenter'];o[1]['sourceUncertainty']=not o[1]['sourceUncertainty']
            self.assertEqual(compare(root,p,e,g,o)['mismatchIndices'],[0,1])
            o[2]['column']+=1
            with self.assertRaises(Exception):compare(root,p,e,g,o)

    def test_truncated_source_never_yields_complete_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,e,g,o=self.fixture(root);part=root/p['polygons']['geometryStore']['parts'][0]['name'];part.write_bytes(part.read_bytes()[:-1])
            with self.assertRaises(Exception):compare(root,p,e,g,o)


if __name__=='__main__':unittest.main()
