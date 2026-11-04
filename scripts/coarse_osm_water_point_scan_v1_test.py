from array import array
from pathlib import Path
import tempfile
import unittest

from assemble_osm_water_polygons_v1 import FEATURE,RING,POINT
from coarse_osm_water_point_scan_v1 import query,location,scan
from prepare_osm_water_catalog_v1_test import store


def geometry(root,features):
    raw=bytearray();identity=1
    for rings in features:
        raw.extend(FEATURE.pack(1,identity,len(rings)));identity+=1
        native=1
        for role,parent,points in rings:
            raw.extend(RING.pack(role,parent,len(points)))
            for index,(x,y) in enumerate(points):
                raw.extend(POINT.pack(1 if index==len(points)-1 else native,x,y));native+=1
    # Each ring's closing native ID must match its own first, not another ring.
    cursor=0
    while cursor<len(raw):
        _,_,count=FEATURE.unpack_from(raw,cursor);cursor+=FEATURE.size
        for _ in range(count):
            _,_,size=RING.unpack_from(raw,cursor);cursor+=RING.size
            first=POINT.unpack_from(raw,cursor);last=cursor+(size-1)*16
            raw[last:last+16]=POINT.pack(first[0],*POINT.unpack_from(raw,last)[1:]);cursor+=size*16
    return store(root,'point-test-geometry',bytes(raw))


class PointControls(unittest.TestCase):
    def test_exact_integer_winding_boundary_and_decimal_precision(self):
        vertices=array('i',[0,0,10,0,10,10,0,10,0,0])
        self.assertEqual(location(query(['0.0000005','0.0000005']),vertices),1)
        self.assertEqual(location(query(['0.000001','0.0000005']),vertices),0)
        self.assertEqual(location(query(['0.000001000000001','0.0000005']),vertices),-1)
        self.assertEqual(location(query(['0.000000999999999','0.0000005']),vertices),1)
        self.assertEqual(location(query([0,0]),vertices),0)

    def test_holes_islands_and_arbitrary_point_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=geometry(root,[[(0,0,[(0,0),(100,0),(100,100),(0,100),(0,0)]),
                                                (1,0,[(20,20),(20,80),(80,80),(80,20),(20,20)]),
                                                (0,2,[(30,30),(60,30),(60,60),(30,60),(30,30)])]])
            xy=[(200,200),(10,10),(25,25),(40,40),(20,40)]
            result=scan(root,report,[[x/1e7,y/1e7] for x,y in xy]);self.assertEqual([r['classification'] for r in result['queries']],
                 ['not_in_accepted_water_geometry','inside_accepted_water','not_in_accepted_water_geometry','inside_accepted_water','on_accepted_water_boundary'])
            self.assertEqual((result['allAcceptedFeaturesScanned'],result['allAcceptedRingsScanned'],result['allAcceptedCoordinateOccurrencesScanned']),(1,3,15))

    def test_overlap_union_does_not_subtract_other_feature_water(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outer=(0,0,[(0,0),(100,0),(100,100),(0,100),(0,0)]);hole=(1,0,[(20,20),(20,80),(80,80),(80,20),(20,20)])
            report=geometry(root,[[outer,hole],[(0,0,[(30,30),(70,30),(70,70),(30,70),(30,30)])]])
            result=scan(root,report,[[0.000005,0.000005],[0.0000025,0.0000025]])
            self.assertEqual(result['queries'][0]['classification'],'inside_accepted_water');self.assertEqual(result['queries'][1]['classification'],'not_in_accepted_water_geometry')

    def test_negative_coordinates_disjoint_boxes_and_query_bounds(self):
        vertices=array('i',[-100,-100,-10,-100,-10,-10,-100,-10,-100,-100])
        self.assertEqual(location(query([-0.000005,-0.000005]),vertices),1)
        for bad in ([181,0],[0,-91],['NaN',0],[True,0],[1],['1e-100',0]):
            with self.assertRaises(Exception):query(bad)

    def test_corrupt_geometry_and_empty_or_excess_query_list_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=store(root,'bad-point-feature',FEATURE.pack(1,1,1)+RING.pack(0,7,4))
            for queries in ([],[[0,0]]*513,[[0,0]]):
                with self.assertRaises(Exception):scan(root,report,queries)


if __name__=='__main__':unittest.main()
