"""Portable all83 road-only witness proof; no local-grid/map admission."""
import json

from verify_multiway_points_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result=previous();report=stage('multiway-road-paths',False)
    assert report['status']=='all83_context_primary_road_witnesses_reproduced'
    assert report['originalCases']==83 and report['valhallaCases']==35
    assert report['paths']==82 and report['unavailable']==1 and len(report['rows'])==83
    expected={row['id']:row['bestRoadTicks'] for row in load(HERE/'multiway-points-raw-v1/report.json')['comparisons']}
    assert {row['id'] for row in report['rows']}==expected.keys()
    for row in report['rows']:
        assert row['primaryRoadTicks']==expected[row['id']]
        if 'unavailable' in row:
            assert expected[row['id']] is None
        else:
            assert sum(row['components'].values())==row['sumTicks']==expected[row['id']]
            assert 0<=row['components']['endpointRoundingTicks']<=7
    assert report['maximumOfflineSearchBackingBytes']==86849616 < 96*1024**2
    assert report['heldCoreGeometryContextBackingBytes']==144055087
    assert report['afterLoad']['arrayBuffers']==report['afterQueries']['arrayBuffers']==144140159
    assert not report['mapsRebuilt'] and not report['localGridWinnerPathsClaimed'] and not report['accuracyOrAppAdmitted']
    assert report['providerRequests']==0
    total=result['newUniqueClosedAllocationBytes']+load(HERE/'multiway-road-paths-closed-v1.json')['usage']['conservativeAllocatedBytes']
    assert total==7376384000
    return {**result,'multiViaAll82PrimaryRoadWitnessesReplayed':True,
            'multiViaPrimaryRoadUnavailableRetained':1,
            'uniqueClosedRoots':257,'newUniqueClosedAllocationBytes':total,
            'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
