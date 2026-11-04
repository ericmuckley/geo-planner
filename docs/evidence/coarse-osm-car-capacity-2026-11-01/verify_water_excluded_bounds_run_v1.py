"""Portable complete excluded-source bounds, retaining geographic uncertainty."""
import json
from verify_water_excluded_bounds_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-excluded-bounds-run',True)
    assert report['status']=='all_excluded_water_source_geometry_bounds_and_saved_point_overlap_complete'
    excluded=report['exclusions'];features=excluded['excludedFeatures'];queries=excluded['queries']
    assert excluded['excludedStandaloneWays']==72 and excluded['excludedRootRelations']==522 and len(features)==594
    assert excluded['sourceReferenceOccurrencesUsedForBounds']==3201109
    assert len(queries)==245 and sum(bool(q['overlappingKnownExcludedSourceBounds']) for q in queries)==12
    unknown=excluded['unboundedOrSourceIncompleteFeatures']
    assert len(unknown)==1 and len(unknown[0]['missingSourceWayIds'])==17 and unknown[0]['missingSourceRelationIds']==[21607544]
    assert sum(not f['allReferencedSourceGeometryBounded'] for f in features)==1
    unsupported=[q for q in queries if q.get('oldSupported') is False]
    assert len(unsupported)==1 and not unsupported[0]['overlappingKnownExcludedSourceBounds']
    assert not unsupported[0]['insideAcceptedWaterFeatures'] and not unsupported[0]['onAcceptedWaterBoundaries']
    assert report['producerNativeTablesReleased'] and not report['sourcePbfReads'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterExcludedSourceBoundsRunCompleted':True,'waterExcludedFeaturesRetainedAndKnownGeometryBounded':594,
            'savedPointsOverlappingKnownExcludedSourceBounds':12,'sourceIncompleteWaterRootsStillSpatiallyUnqualified':1,
            'oldUnsupportedPointInsideAcceptedWaterOrKnownExclusionBounds':False,'outsideAcceptedWaterIsLandProof':False,
            'newUniqueClosedAllocationBytes':5296963584,'uniqueClosedRoots':147,
            'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
