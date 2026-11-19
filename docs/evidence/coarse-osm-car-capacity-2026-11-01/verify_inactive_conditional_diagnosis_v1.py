"""Verify new-epoch source annotations and cached-reference diagnosis, no large reads."""
import json
import math

from verify_inactive_conditional_paths_v1 import verify as previous
from verify_entry_runtime_v1 import stage
from verify_preparation_v1 import HERE, REPO, load, sha


def verify():
    result = previous()
    attributes = stage('inactive-conditional-attributes-run', True)
    paths = load(HERE/'inactive-conditional-paths-v1-raw-v1/report.json')
    candidate = load(HERE/'inactive-conditional-evaluation-v1-raw-v1/report.json')
    assert attributes['paths'] == 83 and attributes['unavailable'] == 0
    assert (attributes['waysChecked'], attributes['preArcMappingsChecked'], attributes['retainedArcMappingsChecked']) == (4227238, 9882872, 9853365)
    assert attributes['sourcePbfReads'] == attributes['routingQueries'] == attributes['providerRequests'] == 0
    assert not attributes['policyFitOrChange'] and not attributes['appActivated']
    epoch = load(HERE/'inactive-conditional-attributes-run-plan-v1.json')
    witness = load(HERE/'inactive-conditional-path-plan-v1.json')
    for key in ('coreManifestSha256', 'geometryManifestSha256'):
        assert epoch[key] == witness[key]
    assert '/inputs/path-report.json' in epoch['mounts'].values()
    assert len(set(epoch['mounts'].values())) == len(epoch['mounts'])
    plan = load(HERE/'inactive-conditional-path-findings-plan-v1.json')
    closed = load(HERE/'inactive-conditional-attributes-run-closed-v1.json')
    for name, pin in plan['bindings'].items():
        if name.startswith('data/'):
            assert name == 'data/coarse-quality/us-osm-inactive-conditional-attributes-run-v1/arc-attributes.json.gz'
            assert pin == closed['roster']['arc-attributes.json.gz']['sha256']
        else:
            assert sha(REPO/name) == pin, name
    findings = load(HERE/'inactive-conditional-path-findings-v1.json')
    assert findings['recipeSha256'] == sha(HERE/'inactive-conditional-path-findings-plan-v1.json')
    assert len(findings['rows']) == 83 and not findings['unavailable']
    assert findings['sourceSpeedAttributeUniqueKnownArcs'] == attributes['selectedArcs']
    assert findings['sourceSpeedAttributeUniqueUnknownArcs'] == 0
    assert findings['providerRequests'] == findings['modelQueries'] == 0 and not findings['policyChanged']
    path_rows = {r['id']: r for r in paths['rows']}
    attr_rows = {r['id']: r for r in attributes['rows']}
    candidate_rows = {r['id']: r for r in candidate['rows']}
    assert set(path_rows) == set(attr_rows) == {r['id'] for r in findings['rows']} == set(candidate_rows)
    for row in findings['rows']:
        assert row['components'] == path_rows[row['id']]['components']
        assert math.isclose(row['candidateMinutes'], path_rows[row['id']]['sumTicks']/480, rel_tol=0, abs_tol=1e-9)
        assert math.isclose(row['candidateMinutes'], candidate_rows[row['id']]['candidate']['pointMinutes'], rel_tol=0, abs_tol=1e-9)
        assert math.isclose(row['signedMinutes'], row['candidateMinutes']-row['referenceMinutes'], rel_tol=0, abs_tol=1e-9)
        exposure = row['sourceSpeedExposure'];attr = attr_rows[row['id']]
        assert exposure['unknownTicks'] == 0
        assert exposure['defaultTicks'] == attr['defaultTicks']
        assert exposure['explicitTicks'] == attr['taggedTicks']
        assert sum(exposure[k] for k in ('explicitTicks','defaultTicks','unknownTicks')) == row['components']['roadTravelTicks']
    for key in ('explicitTicks','defaultTicks','unknownTicks'):
        assert findings['sourceSpeedTickTotals'][key] == sum(r['sourceSpeedExposure'][key] for r in findings['rows'])
    mean = math.fsum(abs(r['signedMinutes']) for r in findings['rows'])/83
    assert math.isclose(mean, findings['overall']['meanAbsoluteErrorMinutes'], rel_tol=0, abs_tol=1e-10)
    assert math.isclose(mean, result['meanAbsoluteMinutes'], rel_tol=0, abs_tol=1e-10)
    total = result['newUniqueClosedAllocationBytes']+closed['usage']['conservativeAllocatedBytes']
    assert total == plan['newClosedAllocationBytes'] and plan['previousClosedRoots'] == 403
    assert 64500000000 + total + 104857600 < 72*1024**3
    return {**result, 'status': 'inactive_conditional_all83_current_winners_source_and_cached_geometry_audited',
            'registeredClosedRoots': 403, 'newUniqueClosedAllocationBytes': total,
            'selectedSourceArcsKnown': attributes['selectedArcs'], 'selectedSourceArcsUnknown': 0,
            'meanSignedMinutes': findings['overall']['meanSignedMinutes'],
            'medianFullGeometryDistanceRatio': findings['overall']['medianFullGeometryDistanceRatio'],
            'meanNonRoadMinutes': findings['overall']['meanNonRoadMinutes'],
            'all166SourceShoreTransferOrAppGatesAdmitted': False}


if __name__ == '__main__':
    print(json.dumps(verify()))
