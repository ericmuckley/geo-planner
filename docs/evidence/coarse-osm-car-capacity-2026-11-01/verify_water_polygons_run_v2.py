"""Portable complete country polygon/source evidence; no mask or ETA admission."""
import json
from verify_water_polygons_controls_v2 import verify as previous
from verify_entry_runtime_v1 import stage


def verify():
    result=previous();report=stage('water-polygons-v2-run',True)
    assert report['status']=='national_saved_water_polygon_feasibility_and_source_replay_complete'
    catalog=report['catalog'];stats=catalog['statistics'];polygons=report['polygons']
    assert stats=={'nodes':101738006,'ways':2829193,'references':104806243,'taggedWays':2374342,'coordinatesSealed':1,'waysSealed':1,'backingBytes':2514354329,'failed':0}
    assert catalog['coordinates']['allSourceCoordinateBytesCompared']==1627808096
    assert catalog['coordinates']['independentDecoderReleasedBeforeWays']
    assert catalog['coordinates']['canonicalSourceShadowSha256']=='5732f7478d89b5dcf5071775f19c795aaa2ed297df03ba501eba952e16b621c2'
    assert catalog['waySourceShadow']=={'bytes':875229453,'sha256':'ce15be065898bea3d38b3ace9865b6d20d75848e03761ff595d93232de8b4418'}
    passed='strict_cached_kernel_geometry_and_source_replay_passed'
    assert sum(polygons['statusCounts']['1'].values())==2374342 and polygons['statusCounts']['1'][passed]==2370883
    assert polygons['statusCounts']['1']['source_member_way_not_independent_water_polygon']==3387
    assert sum(polygons['statusCounts']['2'].values())==68734 and polygons['statusCounts']['2'][passed]==68212
    assert polygons['statusCounts']['3']=={'untagged_descendant_not_independent_root_water_feature':17}
    assert polygons['acceptedFeatures']==polygons['allSavedFeaturesReopened']==2439095
    assert polygons['acceptedRings']==polygons['allSavedRingsReopened']==2648285
    assert polygons['sourcePointsIndependentlyReplayed']==polygons['allSavedNativeCoordinatesReopened']==102511022
    assert polygons['diagnosticsReopened']==2443093
    assert polygons['geometryStore']['rawBytes']==1695719152 and polygons['geometryStore']['compressedBytes']==908221057
    assert polygons['geometryStore']['rawSha256']=='4050d905f60947dfa55d9bf084268d47e42d36feb573ba5c3959b3d6434340d5'
    assert polygons['diagnosticStore']['compressedBytes']==8608811
    assert report['producerNativeTablesReleased'] and not report['sourcePbfReads'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterCountryPolygonRunCompleted':True,'waterCountryPolygonsConstructed':2439095,
            'waterAcceptedPolygonRings':2648285,'waterPolygonNativeCoordinateOccurrencesIndependentlyReplayed':102511022,
            'waterInvalidStandaloneWaysRetained':72,'waterUnresolvedOrInvalidRootRelationsRetained':522,
            'newUniqueClosedAllocationBytes':5290315776,'uniqueClosedRoots':143,
            'waterPolygonsBuiltOrMaskChanged':True,'waterMaskOrModelChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
