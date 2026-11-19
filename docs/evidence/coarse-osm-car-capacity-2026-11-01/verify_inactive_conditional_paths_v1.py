"""Check current-epoch path sums and diagnostic-map identities from saved receipts."""
import json
import math

from verify_inactive_conditional_candidate_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    paths = stage('inactive-conditional-paths-v1')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    by_id = {row['id']: row for row in candidate['rows']}
    assert paths['recipeSha256'] == sha(HERE/'inactive-conditional-path-plan-v1.json')
    assert paths['paths'] == paths['newRoadSearches'] == len(paths['rows']) == 83
    assert {row['id'] for row in paths['rows']} == set(by_id)
    assert paths['unavailable'] == paths['reusedRoadPaths'] == paths['providerRequests'] == 0
    assert not paths['candidateAdmitted']
    assert paths['afterLoad']['arrayBuffers'] == paths['afterQueries']['arrayBuffers']
    for row in paths['rows']:
        assert sum(row['components'].values()) == row['sumTicks']
        assert math.isclose(row['sumTicks']/480, by_id[row['id']]['candidate']['pointMinutes'], rel_tol=0, abs_tol=1e-9)
        assert row['afterReleaseArrayBuffers'] == paths['afterLoad']['arrayBuffers']
        if row['searchStats']:
            assert row['searchStats']['offlineSearchBackingBytes'] <= 96*1024**2
    assert len(paths['phases']) == len(candidate['phases']) == 21
    for phase, original in zip(paths['phases'], candidate['phases']):
        assert phase['origin'] == original['origin']
        assert phase['outputSha256'] == original['diagnostic']['output']['sha256']
        assert phase['fieldStats']['maximumBackingBufferBytes'] < 64*1024**2
        assert phase['traceStats']['productionAlgorithmBackingBufferBytes'] < 64*1024**2
    record = load(HERE/'inactive-conditional-paths-v1-closed-v1.json')
    for row in paths['rows']:
        asset = row['asset'];saved = record['roster'][asset['filename']]
        assert saved['bytes'] == asset['compressedBytes'] and saved['sha256'] == asset['sha256']
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72*1024**3
    return {**result, 'status': 'inactive_conditional_all83_current_winner_sums_and21_maps_reproduced',
            'registeredClosedRoots': 402, 'newUniqueClosedAllocationBytes': total,
            'all83CurrentWinnerSumsReproduced': True, 'all21DiagnosticMapHashesExact': True,
            'all166SourceShoreTransferOrAppGatesAdmitted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
