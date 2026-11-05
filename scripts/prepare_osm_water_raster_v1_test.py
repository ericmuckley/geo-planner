import copy
from pathlib import Path
import tempfile
import unittest

from coarse_osm_water_point_scan_v1_test import geometry
from coarse_osm_water_raster_v1 import WaterRaster
from coarse_osm_water_raster_v1_test import oracle
from prepare_osm_water_raster_v1 import prepare

ARTIFACT=None


class PipelineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Qualified Linux raster artifact required')
        cls.engine=WaterRaster(*ARTIFACT)

    def setUp(self):self.engine.release()
    def tearDown(self):self.engine.release()

    def test_complete_saved_geometry_to_exact_binary_planes_and_uncertainty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rings=[(0,0,[(0,0),(40,0),(40,40),(0,40),(0,0)]),(1,0,[(10,10),(10,30),(30,30),(30,10),(10,10)])]
            source=geometry(root,[rings]);polygon={'polygons':{'geometryStore':source,'acceptedFeatures':1,'acceptedRings':2,'sourcePointsIndependentlyReplayed':10}}
            feature={'knownSourceBoundsE7':[45,5,55,15],'allReferencedSourceGeometryBounded':False}
            exclusion={'exclusions':{'excludedStandaloneWays':0,'excludedRootRelations':1,'excludedFeatures':[feature],'unboundedOrSourceIncompleteFeatures':[{'kind':2,'id':99,'missingSourceWayIds':[123],'missingSourceRelationIds':[]}]}}
            out=root/'out';out.mkdir();result=prepare(out,self.engine,root,polygon,exclusion,(-10,-10,10,8,7))
            expected=oracle((-10,-10,10,8,7),[rings],[([45,5,55,15],False)])
            self.assertEqual([(out/n).read_bytes() for n in ('water-center.bits','source-uncertainty.bits')],expected)
            self.assertFalse(result['manifest']['sourceGeometryCompletelyBounded']);self.assertEqual(result['statistics']['nativeBackingBytes'],14)
            self.assertEqual(result['manifest']['sourceIncompleteFeatures'][0]['missingSourceWayIds'],[123])

    def test_bad_source_population_or_truncated_saved_geometry_stops(self):
        for mode in ('count','source'):
            self.engine.release()
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source=geometry(root,[[(0,0,[(0,0),(30,0),(0,30),(0,0)])]])
                polygon={'polygons':{'geometryStore':source,'acceptedFeatures':1,'acceptedRings':1,'sourcePointsIndependentlyReplayed':4}}
                exclusion={'exclusions':{'excludedStandaloneWays':0,'excludedRootRelations':0,'excludedFeatures':[],'unboundedOrSourceIncompleteFeatures':[]}}
                if mode=='count':polygon['polygons']['acceptedFeatures']=2
                else:
                    path=root/source['parts'][0]['name'];path.write_bytes(path.read_bytes()[:-1])
                out=root/'out';out.mkdir()
                with self.assertRaises(Exception):prepare(out,self.engine,root,polygon,exclusion,(0,0,10,5,5))
                self.assertFalse((out/'manifest.json').exists())


if __name__=='__main__':unittest.main()
