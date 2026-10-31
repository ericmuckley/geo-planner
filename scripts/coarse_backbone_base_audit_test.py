import unittest
from coarse_backbone_base_audit import attribute, link_key


class BaseAttribution(unittest.TestCase):
    def test_all_eight_neighbor_directions_have_symmetric_keys(self):
        width = 5
        for a, b, direction in [(6, 7, 0), (6, 12, 1), (6, 11, 2), (6, 10, 3)]:
            self.assertEqual(link_key(a, b, width, 4), a*4+direction)
            self.assertEqual(link_key(b, a, width, 4), a*4+direction)

    def test_row_wrapping_non_neighbors_and_outside_nodes_are_rejected(self):
        for a, b in [(4, 5), (0, 2), (-1, 0), (0, 20), (0, 0)]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                link_key(a, b, 5, 4)

    def test_exact_source_connector_and_rounding_costs_reconcile(self):
        proof = {'deciseconds': 1501, 'roadKm': 1, 'localKm': .5, 'speedKph': 60,
                 'connectorSpeedKph': 20, 'kind': 'census', 'pointA': [0, 0], 'pointB': [1, 0]}
        edge = {'from': 6, 'target': 7, 'minutes': 1501/600}
        result = attribute(edge, {24: proof}, 5, 4)
        self.assertEqual(result['sourceKind'], 'census')
        self.assertEqual(result['sourceRoadMinutes'], 1)
        self.assertEqual(result['connectorMinutes'], 1.5)
        self.assertAlmostEqual(result['roundingMinutes'], 1/600)

    def test_mismatched_edge_cost_is_rejected(self):
        proof = {'deciseconds': 600}
        with self.assertRaises(ValueError):
            attribute({'from': 6, 'target': 7, 'minutes': 2}, {24: proof}, 5, 4)


if __name__ == '__main__':
    unittest.main()
