"""Synthetic saved-path diagnostics; no graph assets, provider or queries."""
from array import array
import copy
import math
import unittest

from coarse_backbone_codec import encode_signed32
from coarse_backbone_paths import (
    MultiCorridorIndex, account_path, arc_geometry, decode_polyline, overlap, source_samples,
)
from coarse_path_features import distance_km, segment_distance_km


def fixture():
    geometry = encode_signed32([10000, 10000])
    data = {'nodeCoordinates': array('d', [.1, .1, .3, .1]),
            'arcFrom': array('I', [0]), 'arcTo': array('I', [1]),
            'arcMinutes': array('d', [35/85*60]), 'arcRoadKm': array('d', [35]),
            'arcSpeedKph': array('B', [85]), 'arcInteriorOffsets': array('I', [0, 1]),
            'arcByteOffsets': array('I', [0, len(geometry)]),
            'geometryBytes': array('B', geometry), 'interiorSourceKm': array('d', [17.5])}
    transfer = distance_km([.1, .05], [.1, .1])/25*60
    components = {'origin': .4, 'road': data['arcMinutes'][0], 'local': 0.,
                  'transfer': transfer, 'destination': .3}
    path = {'components': components, 'pointMinutes': math.fsum(components.values()), 'direct': None,
            'edges': [{'from': 0, 'target': 4, 'minutes': transfer, 'kind': 'transfer',
                       'fromPoint': [.1, .05], 'toPoint': [.1, .1]},
                      {'from': 4, 'target': 5, 'minutes': data['arcMinutes'][0], 'kind': 'road', 'arc': 0,
                       'fromPoint': [.1, .1], 'toPoint': [.3, .1]}]}
    return data, path


class SavedPathDiagnostics(unittest.TestCase):
    def test_polyline_known_coordinates_and_explicit_precision(self):
        encoded = '_p~iF~ps|U_ulLnnqC_mqNvxq`@'
        points = decode_polyline(encoded, 5)
        self.assertEqual(points, [[-120.2, 38.5], [-120.95, 40.7], [-126.453, 43.252]])
        self.assertEqual(decode_polyline(encoded)[0], [-12.02, 3.85])

    def test_invalid_reference_shapes_are_rejected(self):
        for value in ['', '~', '?', ' ', '~~~~~~~?']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_polyline(value)

    def test_original_cumulative_weights_survive_bent_and_coincident_geometry(self):
        data, _ = fixture()
        points, cumulative = arc_geometry(data, 0)
        self.assertEqual(points, [[.1, .1], [.2, .2], [.3, .1]])
        self.assertEqual(cumulative, [0, 17.5, 35])
        samples = list(source_samples(points, cumulative))
        self.assertAlmostEqual(math.fsum(weight for _, weight in samples), 35)
        coincident = list(source_samples([[0, 0], [0, 0]], [0, 10]))
        self.assertEqual(coincident, [([0., 0.], 10)])

    def test_source_stream_counts_and_cumulative_bounds_reject_corruption(self):
        data, _ = fixture()
        data['interiorSourceKm'][0] = 36
        with self.assertRaises(ValueError):
            arc_geometry(data, 0)
        data, _ = fixture()
        data['arcInteriorOffsets'][1] = 0
        with self.assertRaises(ValueError):
            arc_geometry(data, 0)

    def test_half_integer_source_seed_uses_python_rounding(self):
        data, _ = fixture()
        data['nodeCoordinates'][:2] = array('d', [.000005, -.000005])
        data['geometryBytes'] = array('B', [0, 0])
        data['arcByteOffsets'][1] = 2
        self.assertEqual(arc_geometry(data, 0)[0][1], [0., 0.])

    def test_disconnected_detailed_parts_do_not_create_a_corridor_across_the_gap(self):
        index = MultiCorridorIndex([[[-1, 0], [-.9, 0]], [[.9, 0], [1, 0]]])
        self.assertFalse(index.within([0, 0], 3))
        self.assertTrue(index.within([-.95, 0], .01))

    def test_multi_index_matches_brute_force_at_high_latitudes_and_bins(self):
        parts = [[[-117.15, 49], [-117.05, 49.05]], [[-116.95, 48.95], [-116.85, 49]]]
        index = MultiCorridorIndex(parts)
        for x in range(-8, 9):
            for y in range(-5, 6):
                point = [-117.05+x*.0125, 49+y*.0125]
                expected = any(segment_distance_km(point, a, b) <= 3 for points in parts
                               for a, b in zip(points, points[1:]))
                self.assertEqual(index.within(point, 3), expected)
        self.assertEqual(overlap([], index), {'1': None, '3': None})

    def test_every_captured_source_edge_and_cost_component_reconciles_in_both_directions(self):
        data, path = fixture()
        result = account_path(path, data, 4)
        self.assertAlmostEqual(result['costs']['accountedMinutes'], path['pointMinutes'])
        self.assertEqual(result['costs']['detailedCensusSourceKm'], 35)
        self.assertEqual(result['classes']['85']['edges'], 1)
        reverse = copy.deepcopy(path)
        reverse['edges'] = [reverse['edges'][1]]
        edge = reverse['edges'][0]
        edge['from'], edge['target'] = edge['target'], edge['from']
        edge['fromPoint'], edge['toPoint'] = edge['toPoint'], edge['fromPoint']
        reverse['components']['transfer'] = 0
        reverse['pointMinutes'] = math.fsum(reverse['components'].values())
        result = account_path(reverse, data, 4)
        self.assertTrue(result['audits'][0]['reverse'])
        self.assertEqual(result['parts'][0][0], [.3, .1])

    def test_wrong_source_ids_times_positions_and_underpaid_transfers_fail(self):
        changes = [('minutes', 1), ('target', 9), ('fromPoint', [.11, .1])]
        for name, value in changes:
            data, path = fixture()
            path['edges'][1][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                account_path(path, data, 4)
        data, path = fixture()
        path['edges'][0]['minutes'] = .001
        with self.assertRaises(ValueError):
            account_path(path, data, 4)

    def test_no_detailed_geometry_and_direct_attachments_remain_explicitly_unresolved(self):
        data, _ = fixture()
        components = {'origin': .1, 'road': 1., 'local': 0., 'transfer': 0., 'destination': .2}
        path = {'components': components, 'pointMinutes': 1.3, 'edges': [], 'direct': {'arc': 0}}
        result = account_path(path, data, 4)
        self.assertEqual(result['costs']['unresolvedDirectRoadMinutes'], 1)
        self.assertEqual(result['costs']['detailedCensusTimeShare'], 0)
        self.assertEqual(result['samples'], [])


if __name__ == '__main__':
    unittest.main()
