"""Portable completed source inventory/corridor receipts; no ignored input reads."""
import json

from verify_multi_entry_obstruction_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    assert stage('source-gap-geometry-controls', True)['controls'] == dict(
        tests=12, successful=True, failures=0, errors=0, skips=0)
    capture = stage('source-gap-geometry-capture', True)
    assert (capture['selectedWays'], capture['selectedSourceReferences'], capture['baseIneligibleMajorWays']) == (616, 4322, 249)
    country = stage('source-gap-geometry-run', True)
    assert (country['selectedWays'], country['selectedSourceReferences']) == (52743, 449987)
    assert country['baseIneligibleMajorWays'] == 33683 and country['baseEligibleFinalClosedMajorWays'] == 19060
    assert country['finalClosureIds'] == 29657
    assert country['finalClosureIdsMatchedToMajorWays'] == 19438
    assert country['finalClosureIdsOutsideMajorWayTable'] == 10219
    for report, ways in [(capture, 28995), (country, 4227238)]:
        audit = report['independentAudit']
        assert audit['allWayRowsChecked'] == ways
        assert audit['recordsIndependentlyReplayed'] == report['selectedWays']
        assert audit['sourceReferencesIndependentlyReplayed'] == report['selectedSourceReferences']
        assert report['sourcePbfReads'] == report['sourceConstructorExecutions'] == report['routingQueries'] == report['providerRequests'] == 0
        assert not report['sourcePermissionsOrPricesChanged'] and not report['appActivated']
    plan = load(HERE/'source-gap-corridors-plan-v1.json')
    closed = load(HERE/'source-gap-geometry-run-closed-v1.json')
    artifact = closed['root']+'/geometries.jsonl.gz'
    for name, pin in plan['bindings'].items():
        if name.startswith('data/'):
            assert name == artifact and pin == closed['roster']['geometries.jsonl.gz']['sha256']
        else:
            assert sha(REPO/name) == pin, name
    findings = load(HERE/'source-gap-corridors-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'source-gap-corridors-plan-v1.json')
    assert len(findings['rows']) == findings['allCasesRetained'] == 83
    assert findings['sourceInventoryWays'] == 52743 and findings['sourceInventoryReferences'] == 449987
    assert findings['radiiKm'] == [0.1, 0.25, 1] and findings['winnerGapRadiusKm'] == 1
    assert findings['fractionOfOutsideWinner1KmNearAnyExcluded'] == {
        '0.1': 0.03745977398964682, '0.25': 0.049385214194353245, '1': 0.11989173150310573}
    assert findings['providerRequests'] == findings['modelQueries'] == findings['sourcePbfReads'] == 0
    assert not findings['permissionOrPriceChanges'] and not findings['appActivated']
    stop = load(HERE/'source-gap-corridors-preinput-stop-v1.json')
    assert stop['suppliedPin'] == '0' and not stop['analysisOutputCreated']
    assert stop['sourceDatasetReads'] == stop['routingOrProviderQueries'] == 0
    assert stop['expectedRecipeSha256'] == findings['recipeSha256']
    total = result['newUniqueClosedAllocationBytes']
    for prefix in ('source-gap-geometry-controls', 'source-gap-geometry-capture', 'source-gap-geometry-run'):
        total += load(HERE/(prefix+'-closed-v1.json'))['usage']['conservativeAllocatedBytes']
    assert total == plan['newClosedAllocationBytes'] == 9376387072 and plan['previousClosedRoots'] == 327
    return {**result, 'status': 'complete_excluded_major_geometry_and_all83_cached_corridors_audited',
            'all52743SelectedSourceWaysAnd449987PointsReplayed': True,
            'geometricProximityIsNotIdentityOrPermission': True,
            'registeredClosedRoots': 327, 'newUniqueClosedAllocationBytes': total,
            'accuracyOrAppAccepted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
