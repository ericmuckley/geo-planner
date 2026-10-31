"""Arbitrary rectangles, exact edges and outside-endpoint crossings."""
from fractions import Fraction
import random
import unittest

from coarse_osm_bulk_audit import crossing
from coarse_osm_records import intersects
from coarse_osm_window_cells_v1 import Cells,SCALE,bound
from coarse_timing_input import PilotError


class Tests(unittest.TestCase):
    def test_outside_endpoints_crossing_touching_and_degenerate_segments(self):
        cells=Cells([{'id':'query','bbox':[0,0,1,1]}])
        for points in [[(-1,.5),(2,.5)],[(-1,0),(2,0)],[(0,-1),(0,2)],[(0,0),(0,0)]]:
            encoded=[cells.cell(round(x*SCALE),round(y*SCALE)) for x,y in points]
            self.assertEqual(cells.candidates(encoded),['query'])
        for points in [[(-2,.5),(-1,.5)],[(2,2),(3,3)],[(-1,-1),(-1,-1)]]:
            self.assertEqual(cells.candidates([cells.cell(round(x*SCALE),round(y*SCALE)) for x,y in points]),[])

    def test_exact_integer_edges_and_open_intervals_remain_distinct(self):
        cells=Cells([{'id':'q','bbox':[0,0,1,1]}])
        self.assertEqual([cells.slot(cells.x,x) for x in [-1,0,1,SCALE,SCALE+1]],[0,1,2,3,4])
        self.assertEqual(cells.outcodes(cells.cell(0,0)),b'\x00')
        self.assertEqual(cells.outcodes(cells.cell(-1,-1)),b'\x05')

    def test_non_grid_bounds_expand_using_exact_float_ratios(self):
        for value in [0.,-0.,1e-8,-1e-8,179.123456789,-89.987654321]:
            exact=Fraction(value)*SCALE
            self.assertLessEqual(bound(value),exact);self.assertGreaterEqual(bound(value,True),exact)
            self.assertLessEqual(bound(value,True)-bound(value),1)

    def test_every_cell_class_matches_independent_integer_outcodes(self):
        windows=[{'id':str(i),'bbox':[-170+i*13/2,-80+i*7/2,-169+i*13/2,-79+i*7/2]} for i in range(21)]
        cells=Cells(windows);seen=set()
        xs={-180*SCALE,180*SCALE};ys={-90*SCALE,90*SCALE}
        for edge in cells.x:xs.update([edge-1,edge,edge+1])
        for edge in cells.y:ys.update([edge-1,edge,edge+1])
        for x in xs:
            for y in ys:
                code=cells.cell(x,y);seen.add(code)
                expected=bytes(int(x<left)|2*int(x>right)|4*int(y<bottom)|8*int(y>top) for left,bottom,right,top in cells.boxes)
                self.assertEqual(cells.outcodes(code),expected)
        self.assertEqual(len(seen),7225)

    def test_all_supported_window_counts_fit_uint16_and_fixed_table_bound(self):
        windows=[{'id':str(i),'bbox':[-170+i*13/2,-80+i*7/2,-169+i*13/2,-79+i*7/2]} for i in range(21)]
        cells=Cells(windows)
        self.assertEqual(cells.count,7225);self.assertEqual(len(cells.codes),151725)
        for x,y in [(-180*SCALE,-90*SCALE),(180*SCALE,90*SCALE),(0,0)]:self.assertLess(cells.cell(x,y),65536)

    def test_random_arbitrary_queries_never_reject_either_independent_clip(self):
        randomizer=random.Random(91837);tested=0;rejected=0
        for case in range(100):
            windows=[]
            for i in range(1+case%21):
                x=randomizer.randint(-1700,1700)/10;y=randomizer.randint(-800,800)/10
                windows.append({'id':str(i),'bbox':[x,y,x+randomizer.random()*5,y+randomizer.random()*5]})
            cells=Cells(windows)
            for _ in range(100):
                points=[[randomizer.randint(-180000,180000)/1000,randomizer.randint(-90000,90000)/1000] for _ in range(randomizer.randint(2,6))]
                actual=cells.candidates([cells.cell(round(x*SCALE),round(y*SCALE)) for x,y in points])
                for window in windows:
                    if intersects(points,window['bbox']) or crossing(points,window['bbox']):self.assertIn(window['id'],actual)
                    tested+=1;rejected+=window['id'] not in actual
        self.assertGreater(tested,100000);self.assertGreater(rejected,1000)

    def test_missing_geometry_and_invalid_cells_do_not_become_outside(self):
        cells=Cells([{'id':'q','bbox':[0,0,1,1]}])
        for refs in [[0,None],[0,-1],[0,cells.count],[True,0],[0]]:
            with self.assertRaises(PilotError):cells.candidates(refs)
        for xy in [(True,0),(0,float('nan')),(180*SCALE+1,0)]:
            with self.assertRaises(PilotError):cells.cell(*xy)

    def test_invalid_or_duplicate_queries_fail(self):
        for windows in [[],[{'id':'a','bbox':[1,0,0,1]}],[{'id':'a','bbox':[0,0,1,1]}]*2,[{'id':'a','bbox':[0,0,float('nan'),1]}]]:
            with self.assertRaises(PilotError):Cells(windows)
