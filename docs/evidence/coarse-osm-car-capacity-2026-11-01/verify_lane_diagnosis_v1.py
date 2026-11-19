"""Portable completed current-path/source/cached-geometry diagnosis proof."""
import json

from verify_lane_points_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result=previous();paths=stage('lane-road-paths')
    assert paths['paths']==82 and paths['unavailable']==1 and len(paths['rows'])==83
    assert paths['maximumOfflineSearchBackingBytes']==86886472<96*1024**2
    assert paths['afterLoad']['arrayBuffers']==paths['afterQueries']['arrayBuffers']
    assert paths['providerRequests']==0 and not paths['mapsRebuilt'] and not paths['localGridWinnerPathsClaimed'] and not paths['accuracyOrAppAdmitted']
    assert stage('lane-road-attributes-controls',True)['controls']==dict(tests=9,successful=True,failures=0,errors=0,skips=0)
    attributes=stage('lane-road-attributes-run',True)
    assert (attributes['paths'],attributes['unavailable'],attributes['selectedArcs'])==(82,1,41223)
    assert (attributes['waysChecked'],attributes['preArcMappingsChecked'],attributes['retainedArcMappingsChecked'])==(4227238,9882872,9826630)
    assert attributes['sourcePbfReads']==attributes['routingQueries']==attributes['providerRequests']==0 and not attributes['policyFitOrChange']
    epoch=load(HERE/'lane-road-attributes-run-plan-v1.json');witness=load(HERE/'lane-road-paths-plan-v1.json')
    for name in ('coreManifestSha256','geometryManifestSha256'):assert epoch[name]==witness[name]
    assert epoch['pathAssetPreflight']['finiteAssets']==82 and epoch['pathAssetPreflight']['closedCompressedRawShaAndSourceSumsExact']
    plan=load(HERE/'lane-primary-road-findings-plan-v1.json')
    for name,pin in plan['bindings'].items():assert sha(REPO/name)==pin,name
    report=load(HERE/'lane-primary-road-findings-v1.json')
    assert report['recipeSha256']==sha(HERE/'lane-primary-road-findings-plan-v1.json')
    assert len(report['rows'])==82 and len(report['unavailable'])==1
    assert report['sourceSpeedAttributeUniqueKnownArcs']==41223 and report['sourceSpeedAttributeUniqueUnknownArcs']==0
    assert report['sourceSpeedTickTotals']==dict(explicitTicks=12628639,defaultTicks=1503591,unknownTicks=0)
    assert report['overall']['meanSignedMinutes']==-32.66860264227642
    assert report['overall']['medianFullGeometryDistanceRatio']==0.9984139951165897
    assert report['providerRequests']==report['modelQueries']==0 and not report['policyChanged']
    total=result['newUniqueClosedAllocationBytes']
    for prefix in ('lane-road-paths','lane-road-attributes-controls','lane-road-attributes-run'):total+=load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total==8379293696
    assert plan['previousClosedRoots']==298 and plan['newClosedAllocationBytes']==total
    return {**result,'status':'completed_lane_current_path_source_and_geometry_diagnosis',
            'laneAll82CurrentRoadWitnessesReproduced':True,'laneAll41223SelectedArcSourceAttributesKnown':True,
            'laneRoadMeanSignedMinutes':-32.66860264227642,'laneMedianGeometryDistanceRatio':0.9984139951165897,
            'uniqueClosedRoots':298,'newUniqueClosedAllocationBytes':total,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
