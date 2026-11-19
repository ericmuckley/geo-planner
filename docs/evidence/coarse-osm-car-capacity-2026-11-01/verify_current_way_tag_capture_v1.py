"""Recheck raw-tag coverage and captured collector receipts without large inputs."""
import json

from verify_inactive_conditional_shading_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    plan = load(HERE/'inactive-conditional-source-features-plan-v1.json')
    for name, pin in plan['bindings'].items():
        if not name.startswith('data/'):
            assert sha(REPO/name) == pin, name
    inventory = load(HERE/'inactive-conditional-source-features-v1.json')
    assert inventory['recipeSha256'] == sha(HERE/'inactive-conditional-source-features-plan-v1.json')
    assert (inventory['cachedWayRecordsChecked'], inventory['cachedMajorWayRecordsChecked'], inventory['selectedArcs']) == (239253, 28995, 43910)
    assert (inventory['selectedSourceWays'], inventory['selectedSourceWaysWithCachedRawTags'], inventory['selectedSourceWaysWithoutCachedRawTags']) == (33427, 1084, 32343)
    assert len(inventory['rows']) == len({r['id'] for r in inventory['rows']}) == 83
    for row in inventory['rows']:
        assert row['cachedRawTagTicks'] + row['missingRawSourceTicks'] == row['roadTicks']
        assert set(row['features']) == set(plan['features'])
        for values in row['features'].values():
            assert sum(v['count'] for v in values) == row['cachedRawTagTicks']
            assert len({json.dumps(v['value']) for v in values}) == len(values)
    for values in inventory['cachedMajorWayFeatures'].values():
        assert sum(v['count'] for v in values) == 28995
    for name in ('roadTicks', 'cachedRawTagTicks', 'missingRawSourceTicks'):
        assert inventory[name] == sum(row[name] for row in inventory['rows'])
    assert inventory['roadTicks'] == 15488573 and inventory['cachedRawTagTicks'] == 363566
    assert inventory['sourcePbfReads'] == inventory['newDataAcquired'] == inventory['modelQueries'] == inventory['providerRequests'] == 0
    assert not inventory['policyChanged']
    captured = stage('current-way-tags-source-capture-v1', True)
    raw = HERE/'current-way-tags-source-capture-v1-raw-v1'
    assert load(raw/'audit-controls.json') == dict(tests=10, successful=True, failures=0, errors=0, skips=0)
    assert captured['allCurrentSelectedWays'] == 33427 and captured['cachedOriginalWays'] == 1084
    proof = captured['independentTagAudit'];counts = captured['selectedTags']
    assert proof['selectedWays'] == proof['cachedOriginalsChecked'] == counts['selectedRecords'] == counts['requestedWays'] == 1084
    assert proof['bytes'] == counts['encodedBytes'] == 505704 and proof['tagUtf8Bytes'] == counts['tagUtf8Bytes'] == 344856
    assert captured['allCachedOriginalTagsExact'] and not proof['unknownRawWayIds']
    assert not captured['sourcePermissionsOrPricesChanged'] and not captured['appActivated']
    assert captured['sourcePbfScans'] == captured['sourceConstructorExecutions'] == captured['routingQueries'] == captured['providerRequests'] == captured['applicationDbReads'] == 0
    receipt = load(raw/'receipt.json')
    assert receipt['counts'] == {'way': 1084} and receipt['nativeEof'] and receipt['pythonProjectionFrames'] == 0
    record = load(HERE/'current-way-tags-source-capture-v1-closed-v1.json')
    assert record['roster']['original-way-tags.bin']['sha256'] == proof['sha256']
    metadata = load(raw/'source-inputs-manifest.json')
    assert record['roster']['source-inputs.json.gz']['sha256'] == metadata['sha256']
    assert record['roster']['source-inputs.json.gz']['bytes'] == metadata['bytes']
    total = result['newUniqueClosedAllocationBytes'] + record['usage']['conservativeAllocatedBytes']
    assert 64500000000 + total + 104857600 < 72*1024**3
    return {**result, 'status': 'all_current_way_tag_capture_and_raw_feature_gap_qualified',
            'registeredClosedRoots': 405, 'newUniqueClosedAllocationBytes': total,
            'currentUsedSourceWays': 33427, 'currentCachedRawOriginalsExact': 1084,
            'newActualLinuxAuditControls': 10, 'newNationalSourceCollectionPending': True,
            'rawTimingFeaturesNotYetComplete': True}


if __name__ == '__main__':
    print(json.dumps(verify()))
