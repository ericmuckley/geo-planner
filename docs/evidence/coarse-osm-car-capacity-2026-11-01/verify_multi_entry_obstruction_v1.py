"""Portable negative obstruction finding; no assets, searches or producer replay."""
import json

from verify_tagged_timing_diagnosis_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('multi-entry-obstruction')
    assert report['status'] == 'all83_fixed_winning_attachments_multi_entry_obstruction_probe_complete'
    assert report['originalCases'] == len(report['rows']) == 83 and report['searches'] == 166
    assert report['sourceSupportedStaticBansRetained'] == 235258
    assert report['currentStaticBans'] == 237741 and report['relaxedAdditionalStaticPairs'] == 2483
    assert report['singleViaHistoryStatesRetained'] == 34179
    assert report['allPhysicalCostsAndStartsUnchanged'] and report['allBaselineRoadLegTimesReproduced']
    assert report['staticMethodRestored'] and report['providerRequests'] == report['newMaps'] == 0
    assert not report['candidateAdmitted'] and not report['multiViaPermissionsVerified']
    assert report['afterLoad']['arrayBuffers'] == report['afterQueries']['arrayBuffers'] == 144173575
    improved = [row for row in report['rows'] if row['savingsTicks'] > 0]
    assert report['improvedRoadLegs'] == len(improved) == 1
    assert improved[0]['id'] == 'san-clemente--temecula' and improved[0]['savingsTicks'] == 229
    for row in report['rows']:
        assert row['trialTicks'] <= row['baselineTicks']
        assert row['savingsTicks'] == row['baselineTicks'] - row['trialTicks']
    total = result['newUniqueClosedAllocationBytes'] + load(HERE/'multi-entry-obstruction-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total == 9368297472
    return {**result, 'status': 'multi_entry_fixed_attachment_obstruction_not_a_large_error_driver',
            'all83BaselineRoadLegsReproduced': True, 'optimisticallyImprovedRoadLegs': 1,
            'maximumOptimisticSavingsSeconds': 229 / 8, 'multiViaPermissionsVerified': False,
            'registeredClosedRoots': 324, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
