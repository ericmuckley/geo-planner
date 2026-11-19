"""Portable point-only feasibility proof; frozen maps are not new accuracy."""
import json

from verify_context_wire_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('context-points', False)
    assert report['status'] == 'all83_primary_finish_context_feasibility_complete'
    assert report['originalCases'] == 83 and report['valhallaCases'] == 35
    assert report['allOldFinitePrimaryRoadArrivalsPreserved']
    assert report['changedPointTimes'] == 9 and report['roadFinishesImproved'] == 11
    assert report['contextStates'] == 31692 and report['contextDataBackingBytes'] == 1746705
    assert report['maximumQueryBackingBytes'] == 50937642 < 67108864
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 143986231
    assert report['heldCoreGeometryContextsBackingBytes'] == 143904826
    assert not report['candidateAdmitted'] and report['providerRequests'] == 0
    old = load(HERE/'absent-entry-evaluation-raw-v1/report.json')
    assert len(report['phases']) == 21 and len(report['rows']) == len(report['comparisons']) == 83
    old_rows = {r['id']: r for r in old['rows']}
    timings = {key: value for p in old['phases'] for key, value in p['diagnostic']['timings'].items()}
    new_rows = {r['id']: r for r in report['rows']}
    assert new_rows.keys() == old_rows.keys() == timings.keys()
    finite = 0
    for row in report['comparisons']:
        key = row['id']; saved = timings[key]
        assert row['previousRoadTicks'] == saved['roadTicks']
        if saved['roadTicks'] is not None:
            finite += 1
            assert row['bestRoadTicks'] is not None and row['bestRoadTicks'] <= saved['roadTicks']
        assert row['previousPointTicks'] == saved['ticks'] and row['frozenLocalGridTicks'] == saved['localGridTicks']
        point = min(v for v in (row['bestRoadTicks'], saved['localGridTicks']) if v is not None)
        assert row['pointTicks'] == point and new_rows[key]['candidate']['pointMinutes'] == point/480
        assert new_rows[key]['baseline'] == old_rows[key]['baseline']
        assert new_rows[key]['candidate']['predictedReachable'] == old_rows[key]['candidate']['predictedReachable'] == row['frozenPublicShaded']
        for name in ('origin', 'destination', 'referenceMinutes', 'valhallaMinutes', 'budgetMinutes', 'set'):
            assert new_rows[key][name] == old_rows[key][name]
    assert finite == 82
    assert report['overall']['candidate']['meanAbsoluteMinutes'] == 36.088413654618485
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'context-points-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 6885818368
    return {**result, 'contextAll83PointOnlyProbeComplete': True,
            'contextAll82OldFiniteRoadArrivalsPreserved': True,
            'contextPointOnlyProxyMaeMinutes': 36.088413654618485,
            'uniqueClosedRoots': 236, 'newUniqueClosedAllocationBytes': total,
            'contextMapsRerendered': False, 'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
