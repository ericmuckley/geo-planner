"""Artificial distance ledgers; no model or real-route fixture load."""
import copy
import math
import unittest
from coarse_distance_budget import distance_km, distance_row, endpoint_interval, straight_step, summarize


def fixture():
    edges = [dict(arc=7, **{'from': 1}, target=2, kind='road', minutes=1., fromPoint=[0, 0], toPoint=[.001, 0]),
             dict(arc=7, **{'from': 2}, target=1, kind='road', minutes=1., fromPoint=[.001, 0], toPoint=[0, 0])]
    components = dict(origin=.1, road=2., local=0., transfer=0., destination=.2)
    path = dict(id='frontier/synthetic', direct=None, edges=edges, origin={'lon': 0, 'lat': 0},
                destination={'lon': 0, 'lat': 0}, pointMinutes=2.3, components=components)
    exposure = dict(id=path['id'], oldComponents=components, referenceMinutes=3.3, oldSignedErrorMinutes=-1.,
                    currentSignedErrorMinutes=-.5, sourceMinutesByClass={'85': 0., '105': 2.}, valhallaMinutes=None)
    provider = dict(id=path['id'], origin=path['origin'], destination=path['destination'],
                    candidateMinutes=2.3, orsMinutes=3.3, detailedCensusSourceKm=3.5, orsPolylineKm=4.)
    proofs = [dict(arc=7, sourceKm=1.75, speedKph=105, minutes=1.) for _ in range(2)]
    return [path, exposure, provider, proofs, [], 105]


class DistanceBudgetTests(unittest.TestCase):
    def test_repeated_source_occurrences_preserve_weighted_length(self):
        row, audit = distance_row(*fixture())
        self.assertEqual(row['sourceOccurrences'], 2)
        self.assertEqual(row['detailedSourceKm'], 3.5)
        self.assertEqual(row['distanceMinimumKm'], 3.5)
        self.assertAlmostEqual(row['distanceMaximumKm'], 4.025)
        self.assertEqual(row['lengthStatus'], 'recorded_length_intervals_overlap')
        self.assertEqual(len(audit['edges']), 2)

    def test_endpoint_bounds_do_not_treat_paid_minutes_as_exact_distance(self):
        self.assertEqual(endpoint_interval(0, 105)['maximumKm'], 0)
        self.assertEqual(endpoint_interval(2, 105)['maximumKm'], 3.5)
        self.assertEqual(endpoint_interval(2, 105)['minimumKm'], 0)
        for value in [-1, math.nan, math.inf]:
            with self.assertRaises(ValueError):
                endpoint_interval(value, 105)

    def test_local_and_minimum_transfer_charge(self):
        a, b = [0, 0], [.001, 0]
        raw = distance_km(a, b) / 25 * 60
        local = dict(kind='local', minutes=raw, fromPoint=a, toPoint=b)
        self.assertAlmostEqual(straight_step(local)[0], distance_km(a, b))
        transfer = dict(kind='transfer', minutes=1 / 600, fromPoint=a, toPoint=a)
        self.assertEqual(straight_step(transfer), (0, 1 / 600))
        transfer['minutes'] = 2 / 600
        with self.assertRaises(ValueError):
            straight_step(transfer)

    def test_base_source_and_connector_are_distinct_from_chord(self):
        args = fixture()
        path, exposure, provider, source, base, _ = args
        path['edges'] = [{k: v for k, v in path['edges'][0].items() if k != 'arc'}]
        path['edges'][0]['minutes'] = 2.
        source.clear()
        base.append(dict(key=1, sourceKind='natural-earth', minutes=2., roadKm=2.1, connectorKm=.55,
                         speedKph=105, connectorSpeedKph=55, sourceRoadMinutes=1.2,
                         connectorMinutes=.6, roundingMinutes=.2))
        with self.assertRaisesRegex(ValueError, 'quantization'):
            distance_row(*args)
        base[0].update(connectorKm=.55 * 4 / 3, connectorMinutes=.8, roundingMinutes=0.)
        exposure['sourceMinutesByClass']['105'] = 1.2
        provider['detailedCensusSourceKm'] = 0
        row, _ = distance_row(*args)
        self.assertAlmostEqual(row['knownDistanceKm'], 2.1 + .55 * 4 / 3)
        self.assertEqual(row['baseSourceKm'], 2.1)

    def test_mismatched_or_unused_proof_and_broken_chain_fail(self):
        for mutation in ['arc', 'unused', 'chain']:
            args = fixture()
            if mutation == 'arc':
                args[3][0]['arc'] = 9
            elif mutation == 'unused':
                args[3].append(copy.deepcopy(args[3][0]))
            else:
                args[0]['edges'][1]['from'] = 9
            with self.assertRaises(ValueError):
                distance_row(*args)

    def test_length_classification_is_interval_based(self):
        for reference, expected in [(10, 'recorded_model_shorter'), (1, 'recorded_model_longer')]:
            args = fixture()
            args[2]['orsPolylineKm'] = reference
            row, _ = distance_row(*args)
            self.assertEqual(row['lengthStatus'], expected)
            summary = summarize([row])
            self.assertEqual(summary['statusCounts'][expected], 1)
            self.assertEqual(summary['metrics']['ratioMinimum']['available'], 1)


if __name__ == '__main__':
    unittest.main()
