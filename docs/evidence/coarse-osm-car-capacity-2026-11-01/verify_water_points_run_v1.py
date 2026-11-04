"""Portable complete accepted-water scan for all saved endpoints; no land proof."""
import json
from verify_water_points_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-points-run',True)
    assert report['status']=='all_saved_inputs_and_reference_endpoints_scanned_against_accepted_water_geometry'
    assert report['allAcceptedFeaturesScanned']==2439095 and report['allAcceptedRingsScanned']==2648285
    assert report['allAcceptedCoordinateOccurrencesScanned']==102511022 and len(report['queries'])==245
    assert sum(q['kind']=='input' for q in report['queries'])==79
    assert sum(q['kind']=='returned-reference-endpoint' for q in report['queries'])==166
    assert all(q['classification']=='not_in_accepted_water_geometry' and not q['insideAcceptedWaterFeatures'] and not q['onAcceptedWaterBoundaries'] for q in report['queries'])
    assert sum(q.get('oldSupported') is False for q in report['queries'])==1
    assert not report['sourcePbfReads'] and not report['modelQueries'] and not report['providerRequests'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterSavedEndpointWaterScanCompleted':True,'allSavedInputsAndReturnedEndpointsChecked':245,
            'savedEndpointsInsideAcceptedWater':0,'outsideAcceptedWaterIsLandProof':False,
            'newUniqueClosedAllocationBytes':5293420544,'uniqueClosedRoots':145,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
