"""Independent exhaustive small-cell geometry oracle for the native raster."""
from fractions import Fraction
import gzip
import hashlib
import random
import struct
import unittest

from coarse_osm_water_area_v1_test import inside,meets,on
from coarse_osm_water_raster_v1 import WaterRaster

ARTIFACT=None


def closed(points,role=0,parent=0):
    result=points+[points[0]]
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(result,result[1:]))
    if (area>0)!=(role==0):result=result[::-1]
    return (role,parent,result)


def contains(point,rings):
    # Closed water: ring boundaries are water-center hits AND uncertain.
    groups=set()
    for rank,(role,parent,vertices) in enumerate(rings):
        if any(on(a,b,point) for a,b in zip(vertices,vertices[1:])):return True
        if inside(point,vertices):
            if role==0:groups.add(rank)
            else:groups.discard(parent)
    return bool(groups)


def touches(a,b,box):
    x1,y1,x2,y2=box
    if x1<=a[0]<=x2 and y1<=a[1]<=y2 or x1<=b[0]<=x2 and y1<=b[1]<=y2:return True
    corners=[(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]
    return any(meets(a,b,c,d) for c,d in zip(corners,corners[1:]))


def oracle(grid,features,boxes):
    x,y,step,width,height=grid;water=bytearray((width*height+7)//8);uncertain=bytearray(len(water))
    for row in range(height):
        for col in range(width):
            rectangle=(x+col*step,y+row*step,x+(col+1)*step,y+(row+1)*step)
            center=(Fraction(rectangle[0]+rectangle[2],2),Fraction(rectangle[1]+rectangle[3],2))
            wet=any(contains(center,rings) for rings in features)
            boundary=any(touches(a,b,rectangle) for rings in features for _,_,nodes in rings for a,b in zip(nodes,nodes[1:]))
            boundary|=any(b[0]<=rectangle[2] and b[2]>=rectangle[0] and b[1]<=rectangle[3] and b[3]>=rectangle[1] for b,_ in boxes)
            rank=row*width+col
            if wet:water[rank//8]|=1<<(rank%8)
            if boundary:uncertain[rank//8]|=1<<(rank%8)
    return [bytes(water),bytes(uncertain)]


class RasterControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if ARTIFACT is None:raise unittest.SkipTest('Qualified Linux raster artifact required')
        cls.engine=WaterRaster(*ARTIFACT)

    def setUp(self):self.engine.release()
    def tearDown(self):self.engine.release()

    def raster(self,grid,features,boxes=(),chunk=3):
        self.engine.begin(*grid);rings=points=0
        for feature in features:
            self.engine.call('feature',len(feature));native=1
            for role,parent,vertices in feature:
                self.engine.call('ring',role,parent,len(vertices));raw=bytearray();first=native
                for rank,(x,y) in enumerate(vertices):
                    raw.extend(struct.pack('<Qii',first if rank==len(vertices)-1 else native,x,y));native+=1
                for cursor in range(0,len(raw),16*chunk):self.engine.append_points(bytes(raw[cursor:cursor+16*chunk]))
                rings+=1;points+=len(vertices)
            self.engine.call('feature_finish')
        for bounds,complete in boxes:self.engine.box(bounds,complete)
        self.engine.call('finish',len(features),rings,points,len(boxes),sum(not complete for _,complete in boxes))
        result=self.engine.planes();self.assertEqual(result,oracle(grid,features,boxes))
        self.assertEqual(self.engine.stats()['nativeBackingBytes'],2*((grid[3]*grid[4]+7)//8))
        return result

    def test_holes_islands_and_other_feature_overlap_union(self):
        features=[[closed([(0,0),(90,0),(90,90),(0,90)]),closed([(20,20),(70,20),(70,70),(20,70)],1,0),closed([(30,30),(50,30),(50,50),(30,50)],0,2)],
                  [closed([(40,40),(80,40),(80,80),(40,80)])]]
        self.raster((-10,-10,10,12,12),features)

    def test_grid_lines_corners_horizontal_vertical_diagonal(self):
        for nodes in [[(0,0),(30,0),(30,30),(0,30)],[(0,0),(40,40),(40,0)],[(5,5),(35,5),(35,35),(5,35)],[(0,10),(10,0),(20,10),(10,20)]]:
            self.engine.release();self.raster((-10,-10,10,7,7),[[closed(nodes)]])

    def test_thin_geometry_and_no_center_hit_still_boundary(self):
        result=self.raster((0,0,10,5,5),[[closed([(1,1),(2,1),(2,49),(1,49)])]])
        self.assertFalse(any(result[0]));self.assertTrue(any(result[1]))

    def test_negative_clipped_outside_and_odd_step_centers(self):
        for grid in [(-17,-19,3,11,13),(-40,-30,10,7,5)]:
            self.engine.release();self.raster(grid,[[closed([(-60,-10),(20,-40),(50,20),(-20,50)])]])

    def test_empty_full_grid_and_padding_bits(self):
        for features in ([],[[closed([(-100,-100),(100,-100),(100,100),(-100,100)])]]):
            self.engine.release();self.raster((0,0,3,7,5),features)

    def test_excluded_complete_and_incomplete_bbox_uncertainty_only(self):
        self.raster((-10,-10,10,7,5),[],[([0,0,10,10],True),([25,-30,25,35],False),([-100,-100,-90,-90],True)])

    def test_generated_exhaustive_small_grid_oracle(self):
        rng=random.Random(402914)
        for _ in range(250):
            self.engine.release();grid=(rng.randrange(-20,0),rng.randrange(-20,0),rng.randrange(1,12),rng.randrange(2,9),rng.randrange(2,9));features=[]
            for __ in range(rng.randrange(1,4)):
                x,y=rng.randrange(-30,40),rng.randrange(-30,40);w,h=rng.randrange(2,40),rng.randrange(2,40)
                nodes=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)] if rng.randrange(2) else [(x,y),(x+w,y),(x+w//2,y+h)]
                features.append([closed(nodes)])
            self.raster(grid,features,chunk=rng.randrange(1,8))

    def test_canonical_chunks_and_compressed_binary_roundtrip(self):
        rings=[[closed([(-5,-5),(55,-5),(55,55),(-5,55)]),closed([(10,10),(40,10),(40,40),(10,40)],1,0)]]
        expected=None
        for chunk in (1,2,7,65536):
            self.engine.release();result=self.raster((0,0,5,12,11),rings,chunk=chunk)
            if expected is None:expected=result
            self.assertEqual(result,expected)
            for raw in result:self.assertEqual(gzip.decompress(gzip.compress(raw,mtime=0)),raw)

    def test_bad_counts_closure_roles_state_and_poison_until_release(self):
        for mode in ('count','closure','role','orientation','feature'):
            self.engine.release();self.engine.begin(0,0,10,4,4);self.engine.call('feature',1)
            with self.assertRaises(Exception):
                if mode=='role':self.engine.call('ring',1,0,4)
                elif mode=='feature':self.engine.call('feature_finish')
                else:
                    self.engine.call('ring',0,0,4)
                    nodes=[(1,0,0),(2,30,0),(3,0,30),(1,0,0)]
                    if mode=='closure':nodes[-1]=(9,0,0)
                    if mode=='orientation':nodes=nodes[::-1]
                    self.engine.append_points(b''.join(struct.pack('<Qii',*n) for n in nodes))
                    self.engine.call('feature_finish');self.engine.call('finish',2,1,4,0,0)
            self.assertEqual(self.engine.stats()['failed'],1)
            with self.assertRaisesRegex(Exception,'failed state'):self.engine.call('feature',1)

    def test_domain_capacity_export_and_exact_scratch_release(self):
        self.engine.begin(-1250000000,240000000,50000,11800,5200)
        self.assertEqual(self.engine.stats()['planeBytes'],15340000)
        with self.assertRaises(Exception):self.engine.planes()
        self.engine.call('finish',0,0,0,0,0);self.assertEqual(self.engine.stats()['nativeBackingBytes'],15340000)
        self.engine.release();self.assertEqual(self.engine.stats()['nativeBackingBytes'],0)
        with self.assertRaises(Exception):self.engine.begin(0,0,1,61360001,1)

    def test_bridge_and_artifact_fields(self):
        with self.assertRaises(Exception):WaterRaster(ARTIFACT[0],'0'*64)
        with self.assertRaises(Exception):self.engine.begin(0,0,0.5,10,10)
        self.engine.begin(0,0,10,4,4)
        for raw in (b'',b'x'):
            with self.assertRaises(Exception):self.engine.append_points(raw)
        with self.assertRaises(Exception):self.engine.box([0,0,1,2**32],True)


if __name__=='__main__':unittest.main()
