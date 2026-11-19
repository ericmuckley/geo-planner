"""Portable all83 road/raster delta diagnosis, no model rerun."""
import json
from verify_conditional_evaluation_v1 import verify as previous
from verify_preparation_v1 import HERE, REPO, load, sha
from analyze_osm_conditional_deltas_v1 import changes


def verify():
    result = previous()
    report = load(HERE/'conditional-road-raster-deltas-v1.json')
    expected = changes(load(HERE/'water-country-evaluation-raw-v1/report.json'), load(HERE/'conditional-evaluation-raw-v1/report.json'))
    for key, value in expected.items():
        assert report[key] == value, key
    assert report['producerSha256'] == sha(REPO/'scripts/analyze_osm_conditional_deltas_v1.py')
    for name, pin in report['inputs'].items():
        assert sha(REPO/name) == pin
    assert report['changedPointTimes'] == 21 and len(report['pointIncreases']) == 5
    assert len(report['pointIncreasesWithNonworseRoadAndChangedFrame']) == 5
    assert report['roadRegressions'] == [] and report['casesWithChangedFrame'] == 30
    assert report['providerRequests'] == report['modelQueries'] == 0 and not report['policyChanged']
    return {**result, 'conditionalAll83RoadAndRasterDeltasChecked': True,
            'conditionalPointIncreasesWithNonworseRoadAndChangedFrame': 5,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
