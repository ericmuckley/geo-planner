"""Authenticate completed all-current-way source collection, without source replay."""
import json

from verify_current_way_tag_capture_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, load, sha


def verify():
    result = previous()
    report = stage('current-way-tags-source-run-v1', True)
    root = HERE/'current-way-tags-source-run-v1-raw-v1'
    plan = load(root/'execution-plan.json')
    assert plan['sourceInputPreflight'] == dict(all33427RolesIndependentlyMatchClosed43910SourceArcs=True,
        all1084CachedTagDictionariesMatchCapturedNativeOutput=True, compressedAndRawManifestIdentityExact=True)
    assert plan['capturedAdmission'] == dict(selectedWays=1084, allOriginalTagsExact=True, allCurrentSourceRolesExact=True, auditControls=10)
    assert report['allCurrentSelectedWays'] == 33427 and report['cachedOriginalWays'] == 1084
    counts = report['selectedTags'];audit = report['independentTagAudit']
    assert counts == load(root/'native-counters.json')
    assert counts['requestedWays'] == counts['selectedRecords'] == audit['selectedWays'] == 33427
    assert counts['complete'] == 1 and audit['cachedOriginalsChecked'] == 1084
    assert counts['encodedBytes'] == audit['bytes'] and counts['tagUtf8Bytes'] == audit['tagUtf8Bytes']
    assert not audit['unknownRawWayIds'] and report['allCachedOriginalTagsExact']
    receipt = load(root/'receipt.json')
    expected = {'node':1606229364, 'way':162688797, 'relation':1624265}
    assert receipt['counts'] == expected and receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0
    assert receipt['semanticSha256'] == plan['source']['semanticSha256']
    assert {kind:counts[kind+'s'] for kind in expected} == expected
    assert report['sourcePbfScans'] == 1
    assert report['sourceConstructorExecutions'] == report['routingQueries'] == report['providerRequests'] == report['applicationDbReads'] == 0
    assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    assert load(root/'source-complete.json')['ordinaryPythonProjections'] == 0
    closed = load(HERE/'current-way-tags-source-run-v1-closed-v1.json')
    assert closed['roster']['original-way-tags.bin']['sha256'] == audit['sha256']
    assert closed['roster']['original-way-tags.bin']['bytes'] == audit['bytes']
    assert closed['roster']['way-tags.json.gz']['sha256'] == report['tagArtifact']['sha256']
    assert closed['roster']['way-tags.json.gz']['bytes'] == report['tagArtifact']['bytes']
    assert report['tagArtifact']['rawBytes'] <= 40*1048576 and report['tagArtifact']['bytes'] <= 12*1048576
    total = result['newUniqueClosedAllocationBytes'] + closed['usage']['conservativeAllocatedBytes']
    assert 64500000000+total+104857600 < 72*1024**3
    return {**result, 'status': 'all33427_current_way_original_tags_and_national_source_guards_audited',
            'registeredClosedRoots': 406, 'newUniqueClosedAllocationBytes': total,
            'newNationalSourceCollectionPending': False, 'rawTimingFeaturesNotYetComplete': False,
            'all33427CurrentOriginalWayTagsKnown': True, 'all1084CachedOriginalTagsExact': True,
            'newPricesOrModelQueries': 0}


if __name__ == '__main__':
    print(json.dumps(verify()))
