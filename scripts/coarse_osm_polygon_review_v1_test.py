"""Containment facts retain holes, nonconvex cuts, exact edges and unknown scope."""
from fractions import Fraction
import unittest

from coarse_osm_polygon_review_v1 import parse_poly,review_window,polygon_location
from coarse_timing_input import PilotError


def poly(rings):
    return ('name\n'+''.join(name+'\n'+''.join(f'{x} {y}\n' for x,y in points)+'END\n' for name,points in rings)+'END\n').encode()

SQUARE=[(0,0),(4,0),(4,4),(0,4),(0,0)]


class Tests(unittest.TestCase):
    def test_inside_outside_touch_and_crossing_are_distinct(self):
        rings=parse_poly(poly([('1',SQUARE)]))
        for box,expected in [([1,1,2,2],True),([-2,-2,-1,-1],False),([0,1,1,2],False),([-1,1,1,2],False)]:
            result=review_window({'id':'arbitrary','bbox':box},rings)
            self.assertEqual(result['strictlyInsideReviewedPolygon'],expected);self.assertFalse(result['sourceSnapshotOrRoadCompletenessQualified'])

    def test_hole_inside_window_fails_even_when_all_corners_are_inside(self):
        hole=[(1,1),(2,1),(2,2),(1,2),(1,1)];rings=parse_poly(poly([('1',SQUARE),('!hole',hole)]))
        result=review_window({'id':'q','bbox':[.5,.5,2.5,2.5]},rings)
        self.assertEqual(result['cornerLocations'],['inside']*4);self.assertTrue(result['boundaryTouchesWindow']);self.assertFalse(result['strictlyInsideReviewedPolygon'])
        self.assertEqual(polygon_location((Fraction(3,2),Fraction(3,2)),rings),'outside')

    def test_nonconvex_edge_can_cross_window_with_all_corners_inside(self):
        points=[(0,0),(4,0),(4,4),(2.1,4),(2.1,1),(1.9,1),(1.9,4),(0,4),(0,0)]
        result=review_window({'id':'q','bbox':[1,2,3,3]},parse_poly(poly([('1',points)])))
        self.assertEqual(result['cornerLocations'],['inside']*4);self.assertFalse(result['strictlyInsideReviewedPolygon'])

    def test_ring_order_direction_and_disjoint_polygons_do_not_change_coverage(self):
        other=[(10,10),(11,10),(11,11),(10,11),(10,10)]
        for rings in [[('1',SQUARE),('2',other)],[('2',list(reversed(other))),('1',list(reversed(SQUARE)))]]:
            self.assertTrue(review_window({'id':'q','bbox':[1,1,2,2]},parse_poly(poly(rings)))['strictlyInsideReviewedPolygon'])

    def test_scientific_coordinates_and_exact_float_edges(self):
        rings=parse_poly(b'name\n1\n0 0\n1e-1 0\n1e-1 1e-1\n0 1e-1\n0 0\nEND\nEND\n')
        self.assertEqual(rings[0]['points'][1][0],Fraction(1,10))
        self.assertFalse(review_window({'id':'q','bbox':[0.01,0.01,0.1,0.09]},rings)['strictlyInsideReviewedPolygon'])

    def test_bad_encodings_bounds_and_truncated_rings_fail(self):
        valid=poly([('1',SQUARE)])
        for raw in [b'',b'\xff',valid[:-4],valid+b'junk\n',poly([('1',SQUARE[:-1])]),poly([('1',[(0,0),(1,1),(2,2),(0,0)])]),valid.replace(b'4 0',b'181 0'),valid.replace(b'4 0',b'NaN 0')]:
            with self.assertRaises(PilotError):parse_poly(raw)
        for bbox in [[True,0,1,1],[0,0,float('inf'),1],[1,0,0,1]]:
            with self.assertRaises(PilotError):review_window({'id':'q','bbox':bbox},parse_poly(valid))

    def test_giant_exponents_and_non_decimal_coordinate_syntax_are_rejected(self):
        valid=poly([('1',SQUARE)])
        for value in [b'1e1000000',b'1/3',b'9'*1000]:
            with self.assertRaises(PilotError):parse_poly(valid.replace(b'4 0',value+b' 0'))
