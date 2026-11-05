"""Portable host packet reader/lifetime proof, no route or app admission."""
import json
from verify_water_raster_source_run_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-raster-reader-profile')
    assert report['status']=='host_compact_water_packet_and_arbitrary_observations_passed'
    assert report['packetBackingBytes']==15340000 and report['compressedPlaneBytes']==1781499 and report['manifestBytes']==2007
    assert report['retainedArrayBuffers']==report['afterQueriesArrayBuffers']==15364145
    assert report['releasedArrayBuffers']==report['baselineArrayBuffers']==24145
    rows=report['observations'];assert len(rows)==1002
    assert sum(r['phase']=='saved-point' for r in rows)==245
    assert sum(r['phase']=='saved-cell-center' for r in rows)==245
    assert sum(r['phase']=='generated-cell-center' for r in rows)==512
    assert all(r['kind']=='cell' and r['sourceIncompleteFeatureCount']==1 and not r['sourceGeometryCompletelyBounded'] for r in rows)
    saved=[r for r in rows if r['phase']=='saved-point']
    assert sum(r['sourceUncertainty'] for r in saved)==52 and sum(r['waterAtCenter'] for r in saved)==7
    assert not saved[75]['sourceUncertainty'] and not saved[75]['waterAtCenter']
    assert not report['sourcePbfReads'] and not report['modelQueries'] and not report['providerRequests'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterTypeScriptPacketReaderCountryObservations':1002,'waterReaderBackingBytes':15340000,
            'waterReaderSavedPointsWithSourceUncertainty':52,'newUniqueClosedAllocationBytes':5322055680,'uniqueClosedRoots':152,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
