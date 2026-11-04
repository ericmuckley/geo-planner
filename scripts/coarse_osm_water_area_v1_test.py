"""Tiny exact integer geometry oracle, independent of libosmium, for native controls."""
from collections import Counter
import ctypes
import random
import unittest

from coarse_osm_water_area_v1 import Point,WaterArea

ARTIFACT=None


def ring(points,base=1):
    result=[(base+i,x,y) for i,(x,y) in enumerate(points)]
    return result+[result[0]]


def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def on(a,b,c):return turn(a,b,c)==0 and min(a[0],b[0])<=c[0]<=max(a[0],b[0]) and min(a[1],b[1])<=c[1]<=max(a[1],b[1])


def meets(a,b,c,d):
    first,second,third,fourth=turn(a,b,c),turn(a,b,d),turn(c,d,a),turn(c,d,b)
    return (first*second<0 and third*fourth<0) or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b)


def inside(point,vertices):
    winding=0
    for a,b in zip(vertices,vertices[1:]):
        if on(a,b,point):raise ValueError('Boundary contact')
        if a[1]<=point[1]<b[1] and turn(a,b,point)>0:winding+=1
        if b[1]<=point[1]<a[1] and turn(a,b,point)<0:winding-=1
    return winding!=0


def oracle(rings):
    vertices=[[(x,y) for _,x,y in nodes] for _,nodes in rings];segments=[]
    for rank,points in enumerate(vertices):
        if len(points)<4 or points[0]!=points[-1]:return False
        if not sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:])):return False
        segments.extend((rank,i,a,b) for i,(a,b) in enumerate(zip(points,points[1:])))
    for i,(r,s,a,b) in enumerate(segments):
        for t,u,c,d in segments[i+1:]:
            if r==t and (abs(s-u)==1 or {s,u}=={0,len(vertices[r])-2}):continue
            if meets(a,b,c,d):return False
    for rank,(role,_) in enumerate(rings):
        depth=sum(inside(vertices[rank][0],other) for i,other in enumerate(vertices) if i!=rank)
        if role!=depth%2:return False
    return True


def edges(rings):
    return Counter((role,*sorted((a[0],b[0]))) for role,nodes in rings for a,b in zip(nodes,nodes[1:]))


class WaterAreaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Qualified Linux area artifact required')
        cls.engine=WaterArea(*ARTIFACT)

    def assert_area(self,rings,expected=True):
        self.assertEqual(oracle(rings),expected)
        result=self.engine.assemble(rings);self.assertEqual(result['accepted'],expected,result)
        if not expected:self.assertEqual(result['rings'],[]);return
        output=[(r['role'],r['nodes']) for r in result['rings']]
        self.assertEqual(edges(rings),edges(output));self.assertTrue(oracle(output))
        source={node[0]:node[1:] for _,nodes in rings for node in nodes}
        for r in result['rings']:
            nodes=r['nodes'];self.assertEqual(nodes[0],nodes[-1]);self.assertEqual(len(nodes),len(set(nodes[:-1]))+1)
            self.assertTrue(all(source[n[0]]==n[1:] for n in nodes))
            if r['role']:
                outer=result['rings'][r['parent']];self.assertEqual(outer['role'],0)
                self.assertTrue(inside(nodes[0][1:],[n[1:] for n in outer['nodes']]))

    def test_simple_and_reversed_ring(self):
        nodes=ring([(0,0),(10,0),(10,10),(0,10)])
        self.assert_area([(0,nodes)]);self.assert_area([(0,list(reversed(nodes)))])

    def test_hole_and_all_input_orientations(self):
        outer=ring([(0,0),(100,0),(100,100),(0,100)])
        inner=ring([(20,20),(70,20),(70,70),(20,70)],100)
        for a in (outer,outer[::-1]):
            for b in (inner,inner[::-1]):self.assert_area([(0,a),(1,b)])

    def test_disjoint_outer_and_nested_island(self):
        rings=[(0,ring([(0,0),(100,0),(100,100),(0,100)])),
               (1,ring([(20,20),(80,20),(80,80),(20,80)],100)),
               (0,ring([(30,30),(60,30),(60,60),(30,60)],200)),
               (0,ring([(200,0),(220,0),(220,20),(200,20)],300))]
        self.assert_area(rings)

    def test_concave_outer_with_hole(self):
        self.assert_area([(0,ring([(0,0),(100,0),(100,100),(70,100),(70,30),(30,30),(30,100),(0,100)])),
                          (1,ring([(5,5),(20,5),(20,20),(5,20)],100))])

    def test_wrong_roles_and_holes_outside(self):
        outer=ring([(0,0),(100,0),(100,100),(0,100)])
        inner=ring([(20,20),(70,20),(70,70),(20,70)],100)
        self.assert_area([(0,outer),(0,inner)],False)
        self.assert_area([(1,outer),(0,inner)],False)
        self.assert_area([(1,outer)],False)

    def test_self_intersection_and_overlapping_rings(self):
        self.assert_area([(0,ring([(0,0),(30,40),(0,30),(40,0)]))],False)
        self.assert_area([(0,ring([(0,0),(50,0),(50,50),(0,50)])),
                          (0,ring([(25,25),(75,25),(75,75),(25,75)],100))],False)

    def test_boundary_touch_and_collinear_overlap(self):
        self.assert_area([(0,ring([(0,0),(100,0),(100,100),(0,100)])),
                          (1,ring([(0,20),(30,20),(30,50),(0,50)],100))],False)
        self.assert_area([(0,ring([(0,0),(100,0),(100,100),(0,100)])),
                          (0,ring([(100,20),(150,20),(150,50),(100,50)],100))],False)

    def test_native_identity_preconditions_and_degeneracy(self):
        square=ring([(0,0),(20,0),(20,20),(0,20)])
        variants=[square[:-1],square[:-1]+[(999,0,0)],square[:2]+square[1:],
                  ring([(0,0),(10,0),(20,0)]),ring([(0,0),(0,0),(10,10)]),
                  ring([(-1790000000,0),(1790000000,0),(1790000000,100),(-1790000000,100)]),
                  ring([(0,910000000),(10,910000000),(10,920000000),(0,920000000)])]
        for nodes in variants:
            result=self.engine.assemble([(0,nodes)]);self.assertFalse(result['accepted'],nodes);self.assertFalse(result['rings'])
        self.assertFalse(self.engine.assemble([(0,square),(0,square)])['accepted'])

    def test_distinct_ids_at_same_positions_never_join(self):
        first=ring([(0,0),(20,0),(20,20),(0,20)])
        second=ring([(20,20),(40,20),(40,40),(20,40)],100)
        result=self.engine.assemble([(0,first),(0,second)])
        self.assertFalse(result['accepted']);self.assertIn('coincident',result['reason'])

    def test_generated_exact_integer_oracle(self):
        randomizer=random.Random(8319)
        for _ in range(200):
            x,y=randomizer.randrange(-1000000000,1000000000),randomizer.randrange(-500000000,500000000)
            width,height=randomizer.randrange(20,100000),randomizer.randrange(20,100000)
            outer=ring([(x,y),(x+width,y),(x+width,y+height),(x,y+height)])
            inner=ring([(x+2,y+2),(x+width-2,y+2),(x+width-2,y+height-2),(x+2,y+height-2)],100)
            if randomizer.randrange(2):outer=outer[::-1]
            if randomizer.randrange(2):inner=inner[::-1]
            self.assert_area([(0,outer),(1,inner)])

    def test_callback_boundaries(self):
        # Many distinct collinear points remain exact, across the 64KiB callback boundary.
        points=[(i,0) for i in range(5000)]+[(4999,100),(0,100)]
        result=self.engine.assemble([(0,ring(points))]);self.assertTrue(result['accepted'],result)
        self.assertEqual(edges([(0,ring(points))]),edges([(r['role'],r['nodes']) for r in result['rings']]))

    def test_native_null_offset_and_callback_rejections(self):
        engine=self.engine;points=(Point*4)(Point(1,0,0),Point(2,10,0),Point(3,0,10),Point(1,0,0))
        offsets=(ctypes.c_uint64*2)(0,4);roles=(ctypes.c_uint8*1)(0);error=ctypes.create_string_buffer(512)
        callback=engine.callback(lambda *_:-1)
        self.assertLess(engine.run(points,4,offsets,roles,1,callback,None,error,len(error)),0)
        self.assertLess(engine.run(None,4,offsets,roles,1,callback,None,error,len(error)),0)
        offsets[1]=5
        self.assertLess(engine.run(points,4,offsets,roles,1,callback,None,error,len(error)),0)

    def test_bridge_types_ranges_and_artifact_binding(self):
        for rings in ([],[(2,ring([(0,0),(10,0),(0,10)]))],[(0,[(2**63,0,0)]*4)],[(0,[(1,2**32,0)]*4)]):
            with self.assertRaises(Exception):self.engine.assemble(rings)
        with self.assertRaises(Exception):WaterArea(ARTIFACT[0],'0'*64)


if __name__=='__main__':unittest.main()
