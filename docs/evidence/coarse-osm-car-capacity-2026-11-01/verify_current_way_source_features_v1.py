"""Recompute all complete-source feature exposures from small saved tables."""
import json
from collections import Counter

from verify_current_way_tag_source_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE/'current-way-source-features-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    report = load(HERE/'current-way-source-features-v1.json')
    assert report['recipeSha256'] == sha(HERE/'current-way-source-features-plan-v1.json')
    assert (report['selectedSourceWays'], report['selectedArcs'], report['unknownRawSourceWays']) == (33427, 43910, 0)
    assert len(report['rows']) == len({r['id'] for r in report['rows']}) == 83
    attributes = load(HERE/'inactive-conditional-attributes-run-raw-v1/report.json')
    by_id = {r['id']: r for r in attributes['rows']}
    assert set(by_id) == {r['id'] for r in report['rows']}
    sums = {key: Counter() for key in plan['features']}
    for row in report['rows']:
        assert row['roadTicks'] == row['defaultTicks']+row['explicitTicks'] == by_id[row['id']]['roadTicks']
        assert row['explicitTicks'] == by_id[row['id']]['taggedTicks'] and row['defaultTicks'] == by_id[row['id']]['defaultTicks']
        assert row['missingRawSourceTicks'] == 0 and set(row['features']) == set(plan['features'])
        for key, values in row['features'].items():
            assert sum(v['count'] for v in values) == row['roadTicks']
            assert len({json.dumps(v['value']) for v in values}) == len(values)
            for value in values:
                assert value['count'] >= 0 and type(value['count']) is int
                sums[key][json.dumps(value['value'])] += value['count']
    assert set(report['pathFeatureTickTotals']) == set(report['sourceWayFeatures']) == set(plan['features'])
    for key in plan['features']:
        assert sums[key] == Counter({json.dumps(v['value']): v['count'] for v in report['pathFeatureTickTotals'][key]})
        assert sum(v['count'] for v in report['sourceWayFeatures'][key]) == 33427
    for name in ('roadTicks', 'explicitTicks', 'defaultTicks'):
        assert report[name] == sum(row[name] for row in report['rows'])
    assert report['roadTicks'] == 15488573
    assert report['sourcePbfReads'] == report['newDataAcquired'] == report['modelQueries'] == report['providerRequests'] == 0
    assert not report['policyChanged']
    assert report['rawTagRateComparisons'] == 43910
    mismatches = report['rawTagRateMismatches']
    assert report['rawTagRatesAgreeWithCurrentPolicy'] == (not mismatches)
    assert len({row['arc'] for row in mismatches}) == len(mismatches)
    return {**result, 'status': 'all83_complete_original_source_feature_exposures_independently_recomputed',
            'all83CompleteRawFeatureInventoriesChecked': True,
            'sourceWayTagsKnown': 33427, 'unknownRawSourceWays': 0,
            'sourceFeatureRepricingOrModelQueries': 0,
            'currentRawTagRateComparisons': 43910, 'currentRawTagRateMismatches': len(mismatches)}


if __name__ == '__main__':
    print(json.dumps(verify()))
