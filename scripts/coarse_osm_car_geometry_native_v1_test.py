"""Geometry controls use an independent 3D great-circle projection oracle."""
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest

from coarse_osm_car_geometry_native_v1 import NativeGeometry

ARTIFACT=None
R=6371008.8


def reference(p,a,b):
    def xyz(xy):
        x,y=(math.radians(v/1e7) for v in xy);return (math.cos(y)*math.cos(x),math.cos(y)*math.sin(x),math.sin(y))
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
    def norm(a):return math.sqrt(dot(a,a))
    def angle(a,b):return math.atan2(norm(cross(a,b)),dot(a,b))
    p,a,b=map(xyz,(p,a,b));normal=cross(a,b);length=norm(normal);best=min(angle(p,a),angle(p,b))
    if length<1e-12:return R*best
    normal=tuple(value/length for value in normal);projection=tuple(x-dot(p,normal)*n for x,n in zip(p,normal));size=norm(projection)
    if size<1e-12:return R*best
    q=tuple(value/size for value in projection)
    if angle(a,q)+angle(q,b)<=angle(a,b)+1e-12:best=min(best,angle(p,q))
    return R*best


class GeometryTests(unittest.TestCase):
    def setUp(self):
        if ARTIFACT is None:self.skipTest('Explicit qualified native geometry artifact required')
        self.native=NativeGeometry(*ARTIFACT)

    def test_equator_perpendicular_and_endpoint_projection(self):
        a=(0,0);b=(10000000,0)
        self.assertAlmostEqual(self.native.distance((5000000,100000),a,b),R*math.radians(.01),places=5)
        self.assertAlmostEqual(self.native.distance((20000000,0),a,b),R*math.radians(1),places=5)

    def test_two_thousand_seeded_global_cases_match_3d_oracle(self):
        randomizer=random.Random(20261102)
        for _ in range(2000):
            x=randomizer.uniform(-180,180);y=randomizer.uniform(-80,80)
            def p(dx,dy):return (round(((x+dx+180)%360-180)*1e7),round((y+dy)*1e7))
            a=p(0,0);b=p(randomizer.uniform(-2,2),randomizer.uniform(-2,2));point=p(randomizer.uniform(-2,2),randomizer.uniform(-2,2))
            self.assertAlmostEqual(self.native.distance(point,a,b),reference(point,a,b),delta=.001)

    def test_dateline_pole_and_coincident_endpoints(self):
        for p,a,b in [((1800000000,10000),(1790000000,0),(-1790000000,0)),((0,899900000),(0,899000000),(900000000,899000000)),((10000,0),(0,0),(0,0))]:
            self.assertAlmostEqual(self.native.distance(p,a,b),reference(p,a,b),delta=.001)

    def test_straight_curve_simplifies_to_source_endpoints(self):
        result=self.native.simplify([(i*100000,0) for i in range(101)])
        self.assertEqual(result['kept'],[0,100]);self.assertLessEqual(result['maximumDiscardedErrorMeters'],100)

    def test_bend_and_closed_curve_are_not_collapsed(self):
        self.assertEqual(self.native.simplify([(0,0),(5000000,100000),(10000000,0)])['kept'],[0,1,2])
        self.assertEqual(self.native.simplify([(0,0),(100000,0),(100000,100000),(0,100000),(0,0)])['kept'],[0,1,2,3,4])

    def test_repeated_coordinate_endpoints_remain_distinct_positions(self):
        self.assertEqual(self.native.simplify([(0,0)]*10)['kept'],[0,9])

    def test_invalid_coordinate_tolerance_and_curve_refused(self):
        with self.assertRaises(ValueError):self.native.distance((0,900000001),(0,0),(0,0))
        for tolerance in (0,-1,math.nan,math.inf):
            with self.assertRaises(ValueError):self.native.simplify([(0,0),(1,1)],tolerance)
        with self.assertRaises(ValueError):self.native.simplify([(0,0)])

    def test_small_probe_counts_closures_geometry_and_sparse_shape(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        def save(prefix,fmt,rows):(root/(prefix+'-0000.bin')).write_bytes(b''.join(struct.pack(fmt,*row) for row in rows))
        save('xy','<ii',[(0,0),(5000000,100000),(10000000,0)])
        save('geometry','<I',[(0,),(1,),(2,),(0,),(2,)])
        save('anchors','<I',[(0,),(2,)])
        save('ways','<QddII',[(10,100.,100.,3,3),(20,100.,0.,1,5)])
        save('arcs','<IIIIIb3xQ',[(0,1,0,0,2,1,100000),(1,0,0,0,2,-1,100000),(0,1,1,0,1,1,100000)])
        save('closures','<Q',[(20,)])
        result=self.native.probe(root,[3,2,2,5,3,2])
        self.assertEqual(result['activePhysicalSpans'],1);self.assertEqual(result['sourceInteriorOccurrences'],1)
        self.assertEqual(result['simplifiedInteriorOccurrences'],1);self.assertEqual(result['curvedSpans'],1)
        self.assertEqual(result['spansLongerThan1000m'],1);self.assertEqual(result['longSpanIndexBytesForecast'],19)
        self.assertEqual(sum(row['physicalSpans'] for row in result['lengthHistogram']),1)
        with self.assertRaises(ValueError):self.native.probe(root,[3,2,2,5,3,3])


if __name__=='__main__':unittest.main()
