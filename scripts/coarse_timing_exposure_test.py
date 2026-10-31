"""Artificial saved-record fixtures; no asset or model load."""
import copy
import unittest
from coarse_timing_exposure import cohorts, distribution, join_rows, summarize


def fixture(empty=False):
    detailed = 0 if empty else 60.1
    component = {'origin': 1., 'road': detailed + 30.5, 'local': 2., 'transfer': 3., 'destination': 1.}
    total = sum(component.values())
    c = dict(id='frontier/a', set='frontier', referenceMinutes=total + 10, valhallaMinutes=None,
             budgetMinutes=360, oldSourceMinutes=total, actualAllowanceMinutes=total + 5,
             heldStateMinutes=total + 5, v9Minutes=total + 1,
             oldComponents=component, heldComponents={**component, 'road': component['road'] + 5},
             actualComponents={**component, 'road': component['road'] + 5},
             sourceByClass={'85': 0 if empty else 60., '105': 30.},
             fullRoadSourceMinutes=30. if empty else 90., oldSourceSignedErrorMinutes=-10.,
             actualSignedErrorMinutes=-5., newMissVsV9=False, newMissVsSource=False,
             persistentSourceMiss=False, originalRegressionGateExceeded=False)
    costs = dict(accountedMinutes=total, detailedCensusMinutes=detailed, coarseBaseRoadMinutes=30.5,
                 transferMinutes=3., localMinutes=2., unresolvedOriginMinutes=1.,
                 unresolvedDestinationMinutes=1., unresolvedDirectRoadMinutes=0.)
    p = dict(id=c['id'], set='frontier', orsMinutes=total + 10, candidateMinutes=total, costs=costs,
             classes={} if empty else {'85': {'sourceKm': 85., 'minutes': 60.1, 'edges': 2}},
             detailedCensusSourceKm=0 if empty else 85., detailedEdges=0 if empty else 2,
             detailedCensusTimeShare=detailed / total,
             censusWithin1KmOfOrs=None if empty else .8, censusWithin3KmOfOrs=None if empty else .9,
             orsWithin1KmOfCensusSubset=0 if empty else .6, orsWithin3KmOfCensusSubset=0 if empty else .7)
    edge = dict(sourceKind='natural-earth', roadKm=52.5, speedKph=105, connectorKm=.25,
                connectorSpeedKph=50, sourceRoadMinutes=30., connectorMinutes=.3,
                roundingMinutes=.2, minutes=30.5)
    b = dict(id=c['id'], set='frontier', candidateMinutes=total, groups={'natural-earth': {
        'minutes': 30.5, 'sourceRoadMinutes': 30., 'connectorMinutes': .3,
        'roundingMinutes': .2, 'roadKm': 52.5, 'connectorKm': .25, 'edges': 1}})
    e = dict(id=c['id'], edges=[edge])
    a = dict(id='a', set='frontier', referenceMinutes=total + 10, valhallaMinutes=None,
             budgetMinutes=360, candidate={'pointMinutes': total + 5}, baseline={'pointMinutes': total + 1})
    return [[c], [p], [b], [e], [a]]


class TimingExposureTests(unittest.TestCase):
    def test_source_shares_exclude_connector_rounding_and_endpoints(self):
        row = join_rows(*fixture())[0]
        self.assertEqual(row['sourceMinutes'], 90)
        self.assertAlmostEqual(row['sourceSharesByClass']['85'], 2 / 3)
        self.assertEqual(row['baseConnectorMinutes'], .3)
        self.assertAlmostEqual(row['detailedRoundingMinutes'], .1)
        self.assertEqual(row['endpointMinutes'], 2)

    def test_duplicate_or_missing_identifiers_fail(self):
        for mutation in ('duplicate', 'missing'):
            data = fixture()
            data[1].append(copy.deepcopy(data[1][0])) if mutation == 'duplicate' else data[1].clear()
            with self.assertRaises(ValueError):
                join_rows(*data)

    def test_inconsistent_source_class_component_or_coverage_fails(self):
        for group, field, value in [(0, 'fullRoadSourceMinutes', 99),
                                     (1, 'censusWithin1KmOfOrs', 1.1),
                                     (0, 'oldSourceMinutes', 100)]:
            data = fixture()
            data[group][0][field] = value
            with self.assertRaises(ValueError):
                join_rows(*data)

    def test_missing_detailed_subset_retains_reverse_zero(self):
        row = join_rows(*fixture(True))[0]
        self.assertEqual(row['coverageStatus'], 'no_full_census')
        summary = summarize([row])
        self.assertEqual(summary['metrics']['censusWithin1KmOfOrs']['missing'], 1)
        self.assertEqual(summary['metrics']['orsWithin1KmOfCensusSubset']['median'], 0)
        self.assertEqual(summary['noFullCensus'], 1)

    def test_budget_cohorts_do_not_claim_older_reference_duration(self):
        row = join_rows(*fixture())[0]
        row.update(set='regional', budgetMinutes=720)
        groups = cohorts([row])
        self.assertEqual(len(groups['budget/720']), 1)
        self.assertEqual(len(groups['frontierBudget/720']), 0)
        self.assertEqual(len(groups['oldResidual/faster']), 1)
        self.assertEqual(groups['oldResidual/slower'], [])

    def test_zero_source_has_missing_shares_and_missing_summary_is_explicit(self):
        data = fixture(True)
        for label in ['oldComponents', 'heldComponents', 'actualComponents']:
            data[0][0][label]['road'] -= 30.5
        for field in ['oldSourceMinutes', 'actualAllowanceMinutes', 'heldStateMinutes', 'v9Minutes', 'referenceMinutes']:
            data[0][0][field] -= 30.5
        data[0][0].update(sourceByClass={}, fullRoadSourceMinutes=0)
        for field in ['candidateMinutes', 'orsMinutes']:
            data[1][0][field] -= 30.5
        data[1][0]['costs'].update(accountedMinutes=7., coarseBaseRoadMinutes=0.)
        data[2][0].update(candidateMinutes=7., groups={})
        data[3][0]['edges'] = []
        data[4][0].update(referenceMinutes=17., candidate={'pointMinutes': 12.}, baseline={'pointMinutes': 8.})
        row = join_rows(*data)[0]
        self.assertTrue(all(v is None for v in row['sourceSharesByClass'].values()))
        self.assertEqual(distribution([None, 2, 4])['median'], 3)
        self.assertEqual(distribution([])['available'], 0)
        self.assertIsNone(distribution([])['median'])


if __name__ == '__main__':
    unittest.main()
