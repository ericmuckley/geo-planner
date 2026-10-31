from array import array
import math
import unittest

from coarse_backbone import Components
from coarse_backbone_codec import decode_signed32
from coarse_backbone_geometry import (GeometryGraph, cell, crossings, distance_squared, expanded_path,
                                       grid_axis, quantize_inside, retained_indices, roster, simplify)
from coarse_path_features import distance_km


def graph_for(points):
    coordinates = array('d', points[0] + points[-1])
    graph = GeometryGraph(coordinates)
    km = math.fsum(distance_km(a, b) for a, b in zip(points, points[1:]))
    cost = math.ceil(km/105*36000)
    proof = graph.add_parent(points, 0, 1, km, cost, 105)
    graph.end_part()
    graph.finish_indexes()
    return graph, proof, km, cost


class GeometryTests(unittest.TestCase):
    def test_canonical_half_open_grid_at_negative_and_positive_boundaries(self):
        for boundary in [-100.025, 40.025]:
            expected = round(boundary*40)
            self.assertEqual(grid_axis(boundary), expected)
            self.assertEqual(grid_axis(math.nextafter(boundary, -math.inf)), expected-1)
            self.assertEqual(grid_axis(math.nextafter(boundary, math.inf)), expected)

    def test_true_corner_is_one_exact_parameter(self):
        values = list(crossings([-100.01, 39.99], [-99.99, 40.01]))
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0][1], [-100., 40.])

    def test_near_corner_remains_two_distinct_occurrences(self):
        values = list(crossings([-100.01, 39.99], [-99.99, 40.010000001]))
        self.assertEqual(len(values), 2)
        self.assertLess(values[0][0], values[1][0])

    def test_endpoint_crossings_are_not_duplicated(self):
        self.assertEqual(list(crossings([-100., 40.], [-99.975, 40.])), [])

    def test_repeated_source_positions_have_no_geometric_effect(self):
        a = [[-100.01, 40.01], [-100.01, 40.01], [-99.94, 40.03]]
        b = [a[0], a[-1]]
        self.assertEqual(expanded_path(a), expanded_path(b))

    def test_rdp_retains_a_large_bend_and_drops_a_small_one(self):
        a = [[0,0], [.0001,.001], [.0002,0]]
        self.assertEqual(simplify(a,0,2), [0,1,2])
        a[1][1] = .00001
        self.assertEqual(simplify(a,0,2), [0,2])

    def test_quantization_stays_in_half_open_cell_within_two_meter_allowance(self):
        point = [-100.00000001, 40.024999999]
        key = cell(point)
        quantized = [v/100000 for v in quantize_inside(point,key)]
        self.assertEqual(cell(quantized), key)
        self.assertLess(math.dist(point,quantized)*111320, 2)

    def test_boundary_chord_gets_original_interior_witness(self):
        points = [[-100.02,40.025],[-100.015,40.02499],[-100.01,40.025]]
        owner = cell(points[1])
        self.assertEqual(retained_indices(points,0,2,owner), [0,1,2])
        graph, _, _, _ = graph_for(points)
        self.assertEqual(len(graph.arrays['interiorSourceKm']),1)
        self.assertEqual(graph.cell_mismatches,0)

    def test_tangent_touch_is_protected(self):
        points = [[-100.02,40.02499],[-100.015,40.025],[-100.01,40.02499]]
        _, _, _, protected = expanded_path(points)
        self.assertEqual(protected,[0,1,2])
        graph, _, _, _ = graph_for(points)
        self.assertEqual(len(graph.arrays['crossingFirstArc']),1)
        self.assertEqual(graph.cell_mismatches,0)

    def test_boundary_following_preserves_roster(self):
        graph, _, _, _ = graph_for([[-100.01,40.025],[-99.99,40.025],[-99.96,40.025]])
        self.assertEqual(graph.cell_mismatches,0)

    def test_full_graph_preserves_original_cost_and_positive_crossing_arcs(self):
        graph, proof, km, cost = graph_for([[-100.01,40.01],[-99.94,40.03]])
        arrays = graph.arrays
        self.assertGreater(len(arrays['arcFrom']),1)
        self.assertAlmostEqual(math.fsum(arrays['arcRoadKm']),km)
        self.assertAlmostEqual(math.fsum(arrays['arcMinutes']),cost/600)
        self.assertTrue(all(value>0 for value in arrays['arcMinutes']))
        self.assertEqual(proof['sourceCells'],proof['resultCells'])
        for i, arc in enumerate(arrays['crossingFirstArc']):
            node=graph.original_nodes+i
            self.assertEqual(arrays['arcTo'][arc],node)
            self.assertEqual(arrays['arcFrom'][arc+1],node)
        self.assertEqual(len(arrays['cellArcOffsets']),len(arrays['cellIds'])+1)

    def test_unrelated_grid_crossings_do_not_merge(self):
        coordinates = array('d',[-100.01,40.,-99.99,40.,-100.,39.99,-100.,40.01])
        graph=GeometryGraph(coordinates)
        for a,b in [(0,1),(2,3)]:
            points=[list(coordinates[a*2:a*2+2]),list(coordinates[b*2:b*2+2])]
            km=distance_km(*points)
            graph.add_parent(points,a,b,km,math.ceil(km/105*36000),105)
        uf=Components(len(graph.arrays['nodeCoordinates'])//2)
        for a,b in zip(graph.arrays['arcFrom'],graph.arrays['arcTo']):uf.join(a,b)
        self.assertNotEqual(uf.find(0),uf.find(2))

    def test_interior_geometry_uses_original_cumulative_lengths(self):
        points=[[-100.02,40.005],[-100.015,40.01],[-100.01,40.005]]
        graph, _, km, _=graph_for(points)
        self.assertEqual(len(graph.arrays['arcFrom']),1)
        self.assertAlmostEqual(graph.arrays['interiorSourceKm'][0],km/2,places=5)
        encoded=graph.arrays['geometryBytes']
        values=list(decode_signed32([encoded],100))
        q=[round(v*100000) for v in points[0]]
        q=[q[k]+values[k] for k in [0,1]]
        self.assertLess(math.dist([v/100000 for v in q],points[1])*111320,2)

    def test_constant_segment_distance_is_well_defined(self):
        self.assertEqual(distance_squared([1,0],[0,0],[0,0]),1)
        self.assertEqual(roster([[-100.01,40.01],[-100.01,40.01]]),[cell([-100.01,40.01])])


if __name__=='__main__':
    unittest.main()
