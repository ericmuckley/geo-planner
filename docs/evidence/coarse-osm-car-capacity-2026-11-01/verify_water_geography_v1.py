"""Portable offline geography hypothesis, no route/accuracy/production admission."""
import json
from verify_water_raster_cell_audit_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('water-geography-profile')
    assert report['status']=='host_generic_water_geography_point_and_snap_checks_passed'
    assert len(report['points'])==245 and len(report['segments'])==166
    assert sum(row['legacyMaskAllows'] for row in report['points'])==234
    assert sum(row['newMaskAllows'] for row in report['points'])==245
    assert sum(row['legacyMaskAllows'] for row in report['segments'])==157
    assert sum(row['newMaskAllows'] for row in report['segments'])==166
    assert not report['pointRegressions'] and not report['segmentRegressions']
    assert report['additionalPolicyIndexBackingBytes']==54564
    assert report['retainedArrayBuffers']==report['afterQueriesArrayBuffers']==15491697
    assert report['baselineArrayBuffers']==report['releasedArrayBuffers']==34049
    assert report['packetBackingBytes']==15340000 and report['compressedPlaneBytes']==1781499
    assert report['sourceIncompleteFeatureCount']==1 and report['experimentalMaskHypothesisEvaluated']
    assert not report['sourcePbfReads'] and not report['routingQueries'] and not report['providerRequests'] and not report['productionMaskOrModelChanged'] and not report['appActivated']
    plan=load(HERE/'water-geography-profile-raw-v1/execution-plan.json')
    assert plan['admission']['nodeSyntheticTests']==7 and plan['admission']['strictTypesPassed']
    return {**result,'offlineWaterGeographyHypothesisEvaluated':True,'waterGeographySavedPointsAllowed':245,
            'waterGeographyProviderSnapSegmentsAllowed':166,'waterGeographyOldPositiveRegressions':0,
            'waterGeographyAdditionalIndexBackingBytes':54564,
            'newUniqueClosedAllocationBytes':5326737408,'uniqueClosedRoots':155,
            'waterMaskOrModelChanged':True,'productionMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
