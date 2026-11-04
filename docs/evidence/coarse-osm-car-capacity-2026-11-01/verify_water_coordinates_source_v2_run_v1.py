"""Portable complete national source-coordinate/partition/shadow proof."""
import json
from verify_water_coordinates_source_v2_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE,load


def verify():
    result=previous();report=stage('water-coordinates-source-v2-run',True)
    assert report['status']=='national_water_exact_coordinate_closure_and_source_shadow_audited'
    receipt=load(HERE/'water-coordinates-source-v2-run-raw-v1/receipt.json')
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames']==0
    assert receipt['counts']=={'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['semanticSha256']=='209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    assert receipt['sourceIdentity']['sourceSha256']=='1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    capture=report['coordinates']['capture'];stored=report['coordinates']['stored'];audit=report['independentAudit']
    assert capture['requested']==capture['present']==audit['requestedIdsIndependentlyPartitioned']==audit['presentCoordinatesIndependentlyDecoded']==101738006
    assert capture['missing']==capture['missingBytes']==audit['missingIdsIndependentlyCompared']==0
    assert capture['canonicalBytes']==stored['sourceShadow']['bytes']==audit['allCanonicalSourceIdXYBytesCompared']==1627808096
    assert stored['sourceShadow']['sha256']==audit['canonicalSourceShadowSha256']=='5732f7478d89b5dcf5071775f19c795aaa2ed297df03ba501eba952e16b621c2'
    assert capture['encodedBytes']==stored['encoded']['rawBytes']==582375403
    assert stored['encoded']['rawSha256']=='83a4f7a8be4efa2a614a71a88e5c659fe535a394f3ab007dc5daa2d268f87dc3'
    assert stored['compressedBytes']==stored['encoded']['compressedBytes']==487341692 and stored['missing']['parts']==[]
    assert len(stored['encoded']['parts'])==35 and report['producerBuffersReleasedBeforeAudit']
    assert not report['ringsOrPolygonsConstructed'] and not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterNationalCoordinateCaptureCompleted':True,'waterExactCoordinatesAndPartitionIndependentlyAudited':101738006,
            'waterMissingRequestedNodeIds':0,'waterCoordinateCompressedBytes':487341692,
            'newUniqueClosedAllocationBytes':4282818560,'uniqueClosedRoots':134,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__=='__main__':print(json.dumps(verify()))
