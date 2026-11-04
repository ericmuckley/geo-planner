"""Portable completed national water census; no source/graph/native replay."""
import json
from verify_water_controls_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load


def verify():
    result = previous()
    report = stage('water-source-run', True)
    root = HERE/'water-source-run-raw-v1'
    receipt = load(root/'receipt.json')
    assert report['status'] == 'complete_national_water_metadata_census_passed'
    assert receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0
    assert receipt['counts'] == {'node':1606229364,'way':162688797,'relation':1624265}
    assert receipt['visits'] == 1770542426
    assert receipt['semanticSha256'] == '209cc5927bdd36c667277afd06a4ba301c753797dbf518de7df84e78301d9b16'
    identity = receipt['sourceIdentity']
    assert identity['sourceSha256'] == '1b127070917e2f4e5d9e778e2412bb44d24116519cf084ab72fe13e679eb11ff'
    assert identity['sourceMd5'] == 'c5abaec55e724255277f22fb97941e5a'
    assert identity['framingBytesRead'] == receipt['postSourceHashBytes'] == 12229320016
    assert identity['frames'] == 221321
    water = report['water']
    assert (water['waterWays'],water['waterWayReferences'],water['waterRelations'],water['waterWayMembers']) == (2374342,68013342,68734,468608)
    assert water['closedWaterWays']+water['openWaterWays'] == water['waterWays']
    assert water['outerWayMembers']+water['innerWayMembers']+water['otherRoleWayMembers'] == water['waterWayMembers']
    assert water['complete'] == 1 and not report['coordinatesOrGeometryRetained']
    assert not report['maskOrModelChanged'] and not report['appActivated']
    return {**result,'waterNationalSourceCensusCompleted':True,
            'waterWays':water['waterWays'],'waterWayReferences':water['waterWayReferences'],
            'waterRelations':water['waterRelations'],'waterRelationWayMembers':water['waterWayMembers'],
            'newUniqueClosedAllocationBytes':2859614208,'uniqueClosedRoots':115,
            'waterPolygonsBuiltOrMaskChanged':False,'accuracyOrAppAccepted':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
