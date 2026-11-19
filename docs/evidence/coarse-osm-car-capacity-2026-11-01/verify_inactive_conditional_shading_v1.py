"""Verify current saved-map shoreline observations; do not rerender or admit them."""
import json

from verify_inactive_conditional_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    observed = stage('inactive-conditional-shading')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    assert observed['recipeSha256'] == sha(HERE/'inactive-conditional-shading-plan-v1.json')
    assert len(observed['rows']) == 83 and len(observed['maps']) == 37
    assert observed['baselineArrayBuffers'] == observed['releasedArrayBuffers']
    by_id = {r['id']: r for r in candidate['rows']}
    assert {r['id'] for r in observed['rows']} == set(by_id)
    for row in observed['rows']:
        expected = by_id[row['id']]['candidate']
        assert row['pointMinutes'] == expected['pointMinutes']
        assert row['shaded'] == expected['predictedReachable']
        assert row['classification'] == expected['classification']
    dry_wet = sorted(r['id'] for r in observed['rows'] if r['pointOnMask'] and r['centerOnMask'] is False)
    assert dry_wet == sorted(observed['pointDryButCellCenterWet'])
    missed = [r for r in observed['rows'] if r['classification'] == 'missedReachable']
    assert sorted(r['id'] for r in missed) == sorted(observed['missedReachable'])
    older = [r for r in missed if r['set'] != 'frontier']
    assert len(older) == 1
    row = older[0]
    assert row['pointOnMask'] and row['primaryPaidSegmentAllowed'] and row['centerOnMask'] is False
    assert row['pointMinutes'] < row['budgetMinutes']
    assert all(r['pointMinutes'] > r['budgetMinutes'] for r in missed if r['set'] == 'frontier')
    outputs = [p['output'] for phase in candidate['phases'] for p in phase['productions']]
    assert observed['maps'] == outputs
    closed = load(HERE/'inactive-conditional-evaluation-v1-closed-v1.json')
    for asset in outputs:
        assert all(asset[k] == closed['roster'][asset['filename']][k] for k in ('bytes','sha256'))
    total = result['newUniqueClosedAllocationBytes']+load(HERE/'inactive-conditional-shading-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72*1024**3
    return {**result, 'status': 'inactive_conditional_all83_public_shading_source_cells_audited',
            'registeredClosedRoots': 404, 'newUniqueClosedAllocationBytes': total,
            'all37CurrentPublicMapHashesChecked': True,
            'dryPointsWithClosedDisplayCellCenters': dry_wet,
            'olderMissedPointHasAllowedPaidConnectionAndDryPoint': True,
            'frontierMissesHaveLatePointTimes': True,
            'all166SourceShoreTransferOrAppGatesAdmitted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
